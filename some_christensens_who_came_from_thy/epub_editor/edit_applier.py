"""Apply edits back to HTML files."""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from .models import Correction, EditResult, TextNode
from .html_parser import (
    parse_html_file,
    extract_text_nodes,
    apply_text_replacement,
    save_html_file
)


def create_backup(file_path: Path, backup_dir: Optional[Path] = None) -> Path:
    """Create a backup of the file before modification.

    Args:
        file_path: Path to the file to backup
        backup_dir: Directory to store backups (default: file's directory/.backups)

    Returns:
        Path to the backup file
    """
    if backup_dir is None:
        backup_dir = file_path.parent / ".backups"

    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    backup_path = backup_dir / backup_name

    shutil.copy2(file_path, backup_path)
    return backup_path


def find_node_for_correction(
    correction: Correction,
    text_nodes: list[TextNode]
) -> Optional[TextNode]:
    """Find the TextNode that contains the correction's old_text.

    Args:
        correction: The Correction to find a node for
        text_nodes: List of TextNodes to search

    Returns:
        The first matching TextNode, or None if not found
    """
    for node in text_nodes:
        if correction.old_text in node.extracted_text:
            return node
    return None


def apply_correction(
    correction: Correction,
    node: TextNode
) -> bool:
    """Apply a single correction to a TextNode's element.

    Args:
        correction: The Correction to apply
        node: The TextNode containing the element to modify

    Returns:
        True if the correction was applied, False if old_text wasn't found
    """
    return apply_text_replacement(
        node.element,
        correction.old_text,
        correction.new_text
    )


def apply_corrections_to_file(
    file_path: Path,
    corrections: list[Correction],
    dry_run: bool = False,
    create_backup_file: bool = True
) -> EditResult:
    """Apply all corrections to a single HTML file.

    Args:
        file_path: Path to the HTML file
        corrections: List of corrections to apply
        dry_run: If True, don't actually modify the file
        create_backup_file: If True, create a backup before modifying

    Returns:
        EditResult with details of what was applied
    """
    result = EditResult(file_path=str(file_path))

    try:
        tree = parse_html_file(file_path)
        text_nodes = extract_text_nodes(tree, file_path)
    except Exception as e:
        result.error = f"Failed to parse HTML: {e}"
        return result

    for correction in corrections:
        # Search all nodes for the old_text
        node = find_node_for_correction(correction, text_nodes)

        if node is None:
            print(f"  Warning: Text '{correction.old_text}' not found in any paragraph, skipping")
            result.corrections_skipped.append(correction)
            continue

        if not dry_run:
            success = apply_correction(correction, node)
            if success:
                result.corrections_applied.append(correction)
                print(f"  Applied: '{correction.old_text}' -> '{correction.new_text}' ({correction.reason})")
            else:
                result.corrections_skipped.append(correction)
                print(f"  Failed to apply: '{correction.old_text}' -> '{correction.new_text}'")
        else:
            # In dry run mode, just log what would happen
            result.corrections_applied.append(correction)
            print(f"  Would apply: '{correction.old_text}' -> '{correction.new_text}' ({correction.reason})")

    # Save the modified file
    if not dry_run and result.corrections_applied:
        if create_backup_file:
            backup_path = create_backup(file_path)
            print(f"  Backup created: {backup_path}")

        save_html_file(tree, file_path)
        print(f"  Saved {len(result.corrections_applied)} corrections to {file_path.name}")

    return result
