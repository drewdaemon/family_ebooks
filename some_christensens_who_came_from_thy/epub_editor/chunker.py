"""Text chunking for API token limits."""

import tiktoken
from .models import TextNode, Chunk


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fall back to cl100k_base for unknown models
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def format_node_for_llm(node: TextNode) -> str:
    """Format a text node for inclusion in LLM prompt."""
    return f"[{node.node_id}]\n{node.extracted_text}\n"


def create_chunks(
    text_nodes: list[TextNode],
    max_tokens: int = 2000,
    model: str = "gpt-4"
) -> list[Chunk]:
    """Group TextNodes into chunks that fit within token limits.

    Args:
        text_nodes: List of TextNode objects to chunk
        max_tokens: Maximum tokens per chunk (default 2000)
        model: Model name for token counting

    Returns:
        List of Chunk objects
    """
    chunks = []
    current_nodes = []
    current_text = ""
    current_tokens = 0
    chunk_id = 0

    for node in text_nodes:
        node_text = format_node_for_llm(node)
        node_tokens = count_tokens(node_text, model)

        # If adding this node would exceed the limit, finalize current chunk
        if current_nodes and (current_tokens + node_tokens > max_tokens):
            chunks.append(Chunk(
                chunk_id=chunk_id,
                text_nodes=current_nodes,
                combined_text=current_text.strip(),
                token_count=current_tokens
            ))
            chunk_id += 1
            current_nodes = []
            current_text = ""
            current_tokens = 0

        # Add node to current chunk
        current_nodes.append(node)
        current_text += node_text
        current_tokens += node_tokens

    # Don't forget the last chunk
    if current_nodes:
        chunks.append(Chunk(
            chunk_id=chunk_id,
            text_nodes=current_nodes,
            combined_text=current_text.strip(),
            token_count=current_tokens
        ))

    return chunks
