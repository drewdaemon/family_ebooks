"""Data classes for the EPUB editor."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TextNode:
    """Represents an extractable text element from HTML."""
    node_id: str
    xpath: str
    extracted_text: str
    element: object = field(repr=False)  # lxml Element, excluded from repr


@dataclass
class Chunk:
    """A group of TextNodes that fit within token limits."""
    chunk_id: int
    text_nodes: list[TextNode]
    combined_text: str
    token_count: int


@dataclass
class Correction:
    """A single correction from the LLM."""
    paragraph_id: str
    old_text: str
    new_text: str
    reason: str


@dataclass
class EditResult:
    """Result of applying edits to a file."""
    file_path: str
    corrections_applied: list[Correction] = field(default_factory=list)
    corrections_skipped: list[Correction] = field(default_factory=list)
    error: Optional[str] = None
