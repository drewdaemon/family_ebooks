"""CLI entry point for the EPUB editor."""

import re
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from .html_parser import parse_html_file, extract_text_nodes
from .chunker import create_chunks
from .openai_client import OpenAIEditor
from .edit_applier import apply_corrections_to_file
from .models import Correction


# Load environment variables from .env file
load_dotenv()


def get_html_files(epub_dir: Path) -> list[Path]:
    """Get all index_split_*.html files, sorted by number."""
    pattern = re.compile(r"index_split_(\d+)\.html$")
    files = []

    for f in epub_dir.glob("index_split_*.html"):
        match = pattern.search(f.name)
        if match:
            files.append((int(match.group(1)), f))

    # Sort by the number in the filename
    files.sort(key=lambda x: x[0])
    return [f[1] for f in files]


def filter_files_by_range(
    files: list[Path],
    start: Optional[int],
    end: Optional[int]
) -> list[Path]:
    """Filter files to a specific range (1-indexed, inclusive)."""
    if start is None and end is None:
        return files

    start_idx = (start - 1) if start else 0
    end_idx = end if end else len(files)

    return files[start_idx:end_idx]


def filter_files_by_names(
    files: list[Path],
    names: tuple[str, ...]
) -> list[Path]:
    """Filter files by specific filenames."""
    name_set = set(names)
    return [f for f in files if f.name in name_set]


@click.group()
def cli():
    """EPUB LLM Editor - Edit EPUB files using OpenAI."""
    pass


@cli.command()
@click.argument("epub_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "-i", "--instructions",
    default="",
    help="Custom editing instructions for the LLM"
)
@click.option(
    "-f", "--files",
    multiple=True,
    help="Specific files to process (can be repeated)"
)
@click.option(
    "-r", "--range",
    "file_range",
    nargs=2,
    type=int,
    default=None,
    help="File range to process (start end, 1-indexed inclusive)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without applying them"
)
@click.option(
    "--model",
    default="gpt-5.4-nano",
    help="OpenAI model to use (default: gpt-5.4-nano)"
)
@click.option(
    "--max-tokens",
    default=2000,
    help="Maximum tokens per chunk (default: 2000)"
)
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip creating backup files"
)
def edit(
    epub_dir: Path,
    instructions: str,
    files: tuple[str, ...],
    file_range: Optional[tuple[int, int]],
    dry_run: bool,
    model: str,
    max_tokens: int,
    no_backup: bool
):
    """Edit EPUB HTML files using OpenAI for OCR correction and proofreading.

    EPUB_DIR is the directory containing the index_split_*.html files.
    """
    # Get all HTML files
    all_files = get_html_files(epub_dir)

    if not all_files:
        click.echo(f"Error: No index_split_*.html files found in {epub_dir}")
        sys.exit(1)

    click.echo(f"Found {len(all_files)} HTML files in {epub_dir}")

    # Filter files
    if files:
        target_files = filter_files_by_names(all_files, files)
    elif file_range:
        target_files = filter_files_by_range(all_files, file_range[0], file_range[1])
    else:
        target_files = all_files

    if not target_files:
        click.echo("Error: No files match the specified filter")
        sys.exit(1)

    click.echo(f"Processing {len(target_files)} file(s)")

    if dry_run:
        click.echo("DRY RUN MODE - No changes will be saved")

    # Initialize the OpenAI editor
    try:
        editor = OpenAIEditor(model=model, custom_instructions=instructions)
    except Exception as e:
        click.echo(f"Error initializing OpenAI client: {e}")
        click.echo("Make sure OPENAI_API_KEY is set in your environment or .env file")
        sys.exit(1)

    # Process each file
    total_applied = 0
    total_skipped = 0

    for file_path in target_files:
        click.echo(f"\n{'='*60}")
        click.echo(f"Processing: {file_path.name}")
        click.echo(f"{'='*60}")

        try:
            # Parse the file and extract text nodes
            tree = parse_html_file(file_path)
            text_nodes = extract_text_nodes(tree, file_path)

            if not text_nodes:
                click.echo("  No text content found, skipping")
                continue

            click.echo(f"  Found {len(text_nodes)} text elements")

            # Create chunks for API calls
            chunks = create_chunks(text_nodes, max_tokens=max_tokens, model=model)
            click.echo(f"  Split into {len(chunks)} chunk(s)")

            # Collect all corrections for this file
            all_corrections: list[Correction] = []

            for chunk in chunks:
                click.echo(f"  Processing chunk {chunk.chunk_id + 1}/{len(chunks)} ({chunk.token_count} tokens)...")

                try:
                    corrections = editor.process_chunk(chunk)
                    all_corrections.extend(corrections)

                    if corrections:
                        click.echo(f"    Found {len(corrections)} correction(s)")
                    else:
                        click.echo("    No corrections needed")

                except Exception as e:
                    click.echo(f"    Error processing chunk: {e}")
                    continue

            # Apply corrections
            if all_corrections:
                click.echo(f"\n  Applying {len(all_corrections)} total correction(s)...")
                result = apply_corrections_to_file(
                    file_path,
                    all_corrections,
                    dry_run=dry_run,
                    create_backup_file=not no_backup
                )

                total_applied += len(result.corrections_applied)
                total_skipped += len(result.corrections_skipped)

                if result.error:
                    click.echo(f"  Error: {result.error}")
            else:
                click.echo("\n  No corrections found for this file")

        except Exception as e:
            click.echo(f"  Error processing file: {e}")
            continue

    # Summary
    click.echo(f"\n{'='*60}")
    click.echo("SUMMARY")
    click.echo(f"{'='*60}")
    click.echo(f"Files processed: {len(target_files)}")
    click.echo(f"Corrections applied: {total_applied}")
    click.echo(f"Corrections skipped: {total_skipped}")

    if dry_run:
        click.echo("\nDRY RUN - No files were modified")


@cli.command()
@click.argument("epub_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def list_files(epub_dir: Path):
    """List all index_split_*.html files in the EPUB directory."""
    files = get_html_files(epub_dir)

    if not files:
        click.echo(f"No index_split_*.html files found in {epub_dir}")
        return

    click.echo(f"Found {len(files)} files:")
    for i, f in enumerate(files, 1):
        click.echo(f"  {i:3d}. {f.name}")


def main():
    cli()


if __name__ == "__main__":
    main()
