"""HTML parsing and text extraction for EPUB files."""

from pathlib import Path
from lxml import etree
from .models import TextNode


# XHTML namespace used in EPUB files
XHTML_NS = "http://www.w3.org/1999/xhtml"
NSMAP = {"xhtml": XHTML_NS}


def parse_html_file(file_path: Path) -> etree._ElementTree:
    """Parse an XHTML file and return the element tree."""
    parser = etree.XMLParser(remove_blank_text=False)
    return etree.parse(str(file_path), parser)


def extract_text_nodes(tree: etree._ElementTree, file_path: Path) -> list[TextNode]:
    """Extract all text-containing elements (p, h1, h2, h3, etc.) from the document.

    Returns a list of TextNode objects with extracted plain text.
    """
    root = tree.getroot()
    text_nodes = []

    # Find all paragraph and heading elements
    # Using local-name() to handle namespaced elements
    xpath_expr = "//*[local-name()='p' or local-name()='h1' or local-name()='h2' or local-name()='h3']"
    elements = root.xpath(xpath_expr)

    for idx, element in enumerate(elements):
        # Generate a unique node ID based on file and position
        file_stem = file_path.stem
        node_id = f"{file_stem}_p{idx:03d}"

        # Get the xpath for this element
        xpath = tree.getpath(element)

        # Extract plain text content (stripping inline HTML)
        text_content = get_text_content(element)

        if text_content.strip():  # Only include non-empty nodes
            text_nodes.append(TextNode(
                node_id=node_id,
                xpath=xpath,
                extracted_text=text_content,
                element=element
            ))

    return text_nodes


def get_text_content(element: etree._Element) -> str:
    """Extract plain text from an element, preserving text order but stripping tags.

    This recursively collects all text content from the element and its children.
    """
    texts = []

    # Get the element's direct text
    if element.text:
        texts.append(element.text)

    # Get text from children and their tails
    for child in element:
        # Recursively get child text
        texts.append(get_text_content(child))
        # Get the tail text (text after the child element)
        if child.tail:
            texts.append(child.tail)

    return "".join(texts)


def apply_text_replacement(element: etree._Element, old_text: str, new_text: str) -> bool:
    """Replace old_text with new_text in the element's text content.

    This handles text that may be split across the element's .text
    and child element .tail attributes.

    Returns True if replacement was made, False otherwise.
    """
    # First check if the text exists in the full content
    full_text = get_text_content(element)
    if old_text not in full_text:
        return False

    # Try to replace in the element's direct text
    if element.text and old_text in element.text:
        element.text = element.text.replace(old_text, new_text, 1)
        return True

    # Try to replace in child tails
    for child in element:
        if child.tail and old_text in child.tail:
            child.tail = child.tail.replace(old_text, new_text, 1)
            return True

    # Handle case where text spans across element.text and child.tail
    # This is more complex - we need to concatenate and find boundaries
    return _apply_spanning_replacement(element, old_text, new_text)


def _apply_spanning_replacement(element: etree._Element, old_text: str, new_text: str) -> bool:
    """Handle replacements that span across text nodes.

    This is needed when old_text starts in one text node and ends in another.
    """
    # Build a map of text segments with their locations
    segments = []

    if element.text:
        segments.append(("element.text", element.text, element, "text"))

    for child in element:
        if child.tail:
            segments.append((f"child.tail", child.tail, child, "tail"))

    # Concatenate all text
    full_text = "".join(seg[1] for seg in segments)

    # Find the position of old_text
    pos = full_text.find(old_text)
    if pos == -1:
        return False

    end_pos = pos + len(old_text)

    # Find which segments are affected
    current_pos = 0
    for i, (name, text, obj, attr) in enumerate(segments):
        seg_start = current_pos
        seg_end = current_pos + len(text)

        # Check if old_text starts in this segment
        if seg_start <= pos < seg_end:
            # Check if it also ends in this segment
            if end_pos <= seg_end:
                # Simple case: contained in one segment
                if attr == "text":
                    obj.text = text[:pos - seg_start] + new_text + text[end_pos - seg_start:]
                else:
                    obj.tail = text[:pos - seg_start] + new_text + text[end_pos - seg_start:]
                return True
            else:
                # Complex case: spans multiple segments
                # Replace what's in this segment, clear subsequent affected text
                prefix = text[:pos - seg_start]
                if attr == "text":
                    obj.text = prefix + new_text
                else:
                    obj.tail = prefix + new_text

                # Clear text from subsequent segments until we've removed old_text
                remaining_to_remove = end_pos - seg_end
                for j in range(i + 1, len(segments)):
                    _, seg_text, seg_obj, seg_attr = segments[j]
                    if remaining_to_remove >= len(seg_text):
                        # Clear this entire segment
                        if seg_attr == "text":
                            seg_obj.text = ""
                        else:
                            seg_obj.tail = ""
                        remaining_to_remove -= len(seg_text)
                    else:
                        # Partial clear
                        if seg_attr == "text":
                            seg_obj.text = seg_text[remaining_to_remove:]
                        else:
                            seg_obj.tail = seg_text[remaining_to_remove:]
                        break

                return True

        current_pos = seg_end

    return False


def save_html_file(tree: etree._ElementTree, file_path: Path) -> None:
    """Save the modified tree back to file."""
    tree.write(
        str(file_path),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=False  # Preserve original formatting
    )
