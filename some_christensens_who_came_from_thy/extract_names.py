#!/usr/bin/env python3
"""Extract people and place names from EPUB files using OpenAI API.

This script analyzes EPUB HTML files and extracts all names (people and places)
along with their variants, outputting both JSON and CSV formats.

Usage:
    python extract_names.py --epub-dir epub/ --output names
    python extract_names.py --epub-dir epub/ --range 1 5 --dry-run
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from epub_editor.html_parser import parse_html_file, extract_text_nodes
from epub_editor.chunker import create_chunks
from epub_editor.name_extractor import (
    NameExtractor,
    aggregate_names,
    AggregatedName,
    ExtractedName
)


def get_html_files(epub_dir: Path, file_range: tuple[int, int] | None = None) -> list[Path]:
    """Get sorted list of HTML files from the EPUB directory.

    Args:
        epub_dir: Path to the EPUB directory
        file_range: Optional (start, end) tuple for file indices (1-indexed, inclusive)

    Returns:
        List of Path objects for HTML files
    """
    html_files = sorted(epub_dir.glob("index_split_*.html"))

    if file_range:
        start, end = file_range
        # Convert to 0-indexed
        html_files = html_files[start - 1:end]

    return html_files


def extract_from_file(
    file_path: Path,
    extractor: NameExtractor,
    dry_run: bool = False
) -> list[ExtractedName]:
    """Extract names from a single HTML file.

    Args:
        file_path: Path to the HTML file
        extractor: NameExtractor instance
        dry_run: If True, skip actual API calls

    Returns:
        List of ExtractedName objects
    """
    # Parse HTML and extract text nodes
    tree = parse_html_file(file_path)
    text_nodes = extract_text_nodes(tree, file_path)

    if not text_nodes:
        return []

    # Create chunks for processing
    chunks = create_chunks(text_nodes, max_tokens=3000)

    all_names = []

    for chunk in chunks:
        if dry_run:
            print(f"  [DRY RUN] Would process chunk {chunk.chunk_id} ({chunk.token_count} tokens)")
            continue

        try:
            names = extractor.extract_names(chunk.combined_text, source_file=file_path.name)
            all_names.extend(names)
        except Exception as e:
            print(f"  Error processing chunk {chunk.chunk_id}: {e}")
            continue

    return all_names


def build_output_json(
    aggregated: dict[str, AggregatedName],
    source_files: list[str]
) -> dict:
    """Build the JSON output structure.

    Args:
        aggregated: Dictionary of aggregated names
        source_files: List of source file names

    Returns:
        Dictionary ready for JSON serialization
    """
    people = []
    places = []

    for name_data in aggregated.values():
        entry = {
            "name": name_data.name,
            "variants": name_data.variants,
            "occurrences": [
                {"file": occ.file, "context": occ.context}
                for occ in name_data.occurrences
            ]
        }

        if name_data.name_type == "person":
            people.append(entry)
        else:
            places.append(entry)

    # Sort by name
    people.sort(key=lambda x: x["name"].lower())
    places.sort(key=lambda x: x["name"].lower())

    return {
        "extraction_date": datetime.now().strftime("%Y-%m-%d"),
        "source_files": source_files,
        "people": people,
        "places": places
    }


def write_csv(aggregated: dict[str, AggregatedName], output_path: Path) -> None:
    """Write extracted names to CSV format.

    Args:
        aggregated: Dictionary of aggregated names
        output_path: Path to output CSV file
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "name", "variants", "first_occurrence_file", "context_snippet"])

        # Sort by type then name
        sorted_names = sorted(
            aggregated.values(),
            key=lambda x: (x.name_type, x.name.lower())
        )

        for name_data in sorted_names:
            first_occ = name_data.occurrences[0] if name_data.occurrences else None
            writer.writerow([
                name_data.name_type,
                name_data.name,
                "; ".join(name_data.variants),
                first_occ.file if first_occ else "",
                first_occ.context if first_occ else ""
            ])


def main():
    parser = argparse.ArgumentParser(
        description="Extract people and place names from EPUB files using OpenAI API"
    )
    parser.add_argument(
        "--epub-dir",
        type=Path,
        required=True,
        help="Path to the EPUB directory containing HTML files"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="names",
        help="Output filename base (will create <name>.json and <name>.csv)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--range",
        type=int,
        nargs=2,
        metavar=("START", "END"),
        help="Process only files in range (1-indexed, inclusive)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making API calls"
    )

    args = parser.parse_args()

    # Validate epub directory
    if not args.epub_dir.is_dir():
        print(f"Error: EPUB directory not found: {args.epub_dir}")
        sys.exit(1)

    # Get HTML files to process
    file_range = tuple(args.range) if args.range else None
    html_files = get_html_files(args.epub_dir, file_range)

    if not html_files:
        print(f"Error: No HTML files found in {args.epub_dir}")
        sys.exit(1)

    print(f"Found {len(html_files)} HTML files to process")

    if args.dry_run:
        print("\n[DRY RUN MODE - No API calls will be made]\n")

    # Initialize extractor (only if not dry-run)
    extractor = None if args.dry_run else NameExtractor(model=args.model)

    # Process each file
    all_extractions: list[tuple[str, list[ExtractedName]]] = []

    for i, file_path in enumerate(html_files, 1):
        print(f"[{i}/{len(html_files)}] Processing {file_path.name}...")

        names = extract_from_file(file_path, extractor, dry_run=args.dry_run)

        if names:
            all_extractions.append((file_path.name, names))
            print(f"  Found {len([n for n in names if n.name_type == 'person'])} people, "
                  f"{len([n for n in names if n.name_type == 'place'])} places")

    if args.dry_run:
        print("\n[DRY RUN] Would aggregate and write results")
        return

    # Aggregate names across all files
    print("\nAggregating names...")
    aggregated = aggregate_names(all_extractions)

    # Count by type
    people_count = sum(1 for n in aggregated.values() if n.name_type == "person")
    places_count = sum(1 for n in aggregated.values() if n.name_type == "place")
    print(f"Found {people_count} unique people, {places_count} unique places")

    # Build and write JSON output
    json_output = build_output_json(
        aggregated,
        source_files=[f.name for f in html_files]
    )

    json_path = Path(f"{args.output}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    print(f"\nWrote JSON output to {json_path}")

    # Write CSV output
    csv_path = Path(f"{args.output}.csv")
    write_csv(aggregated, csv_path)
    print(f"Wrote CSV output to {csv_path}")


if __name__ == "__main__":
    main()
