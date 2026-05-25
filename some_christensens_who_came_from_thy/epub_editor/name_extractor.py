"""OpenAI API integration for name extraction from historical texts."""

import json
import os
from dataclasses import dataclass, field
from typing import Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APITimeoutError


SYSTEM_PROMPT = """You are analyzing historical family history text to extract names.

Extract all:
1. PEOPLE NAMES - Include full names, nicknames, maiden names, married names
2. PLACE NAMES - Cities, regions, farms, churches, countries

For each name, identify variants (different spellings, abbreviations, translations between Danish/English).

Return JSON:
{
  "people": [
    {"name": "primary name form", "variants": ["variant1", "variant2"], "context": "brief phrase showing how name appears"}
  ],
  "places": [
    {"name": "primary name form", "variants": ["variant1", "variant2"], "context": "brief phrase showing how name appears"}
  ]
}

Guidelines:
- Use the most complete/formal version as the primary "name"
- Include abbreviated forms, nicknames, and alternate spellings in "variants"
- For Danish names, include both Danish and English forms if present
- "context" should be a short snippet (5-15 words) showing how the name appears in text
- Return empty arrays if no names found: {"people": [], "places": []}
- Include each unique person/place only once per response"""


@dataclass
class ExtractedName:
    """A single extracted name with its variants."""
    name: str
    variants: list[str] = field(default_factory=list)
    context: str = ""
    name_type: str = ""  # "person" or "place"


@dataclass
class NameOccurrence:
    """Records where a name was found."""
    file: str
    context: str


@dataclass
class AggregatedName:
    """A name aggregated across multiple chunks/files."""
    name: str
    name_type: str  # "person" or "place"
    variants: list[str] = field(default_factory=list)
    occurrences: list[NameOccurrence] = field(default_factory=list)


class NameExtractor:
    """Handles OpenAI API calls for extracting names from text."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None
    ):
        self.model = model
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            timeout=60.0
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError))
    )
    def extract_names(self, text: str, source_file: str = "") -> list[ExtractedName]:
        """Send text to OpenAI for name extraction.

        Args:
            text: The text to analyze for names
            source_file: Optional source file name for context

        Returns:
            List of ExtractedName objects
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        return self.parse_response(response.choices[0].message.content)

    def parse_response(self, response_text: str) -> list[ExtractedName]:
        """Parse the JSON response from OpenAI into ExtractedName objects.

        Args:
            response_text: The raw JSON string from the API

        Returns:
            List of ExtractedName objects
        """
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse JSON response: {e}")
            return []

        names = []

        # Parse people
        for item in data.get("people", []):
            try:
                names.append(ExtractedName(
                    name=item["name"],
                    variants=item.get("variants", []),
                    context=item.get("context", ""),
                    name_type="person"
                ))
            except KeyError as e:
                print(f"Warning: Skipping malformed person entry (missing {e}): {item}")
                continue

        # Parse places
        for item in data.get("places", []):
            try:
                names.append(ExtractedName(
                    name=item["name"],
                    variants=item.get("variants", []),
                    context=item.get("context", ""),
                    name_type="place"
                ))
            except KeyError as e:
                print(f"Warning: Skipping malformed place entry (missing {e}): {item}")
                continue

        return names


def aggregate_names(
    all_names: list[tuple[str, list[ExtractedName]]]
) -> dict[str, AggregatedName]:
    """Aggregate names extracted from multiple files, deduplicating and merging variants.

    Args:
        all_names: List of (source_file, extracted_names) tuples

    Returns:
        Dictionary mapping normalized name to AggregatedName
    """
    aggregated: dict[str, AggregatedName] = {}

    for source_file, names in all_names:
        for extracted in names:
            # Normalize the name for lookup (lowercase, stripped)
            key = f"{extracted.name_type}:{extracted.name.lower().strip()}"

            if key in aggregated:
                # Merge variants
                existing = aggregated[key]
                for variant in extracted.variants:
                    if variant not in existing.variants and variant.lower() != existing.name.lower():
                        existing.variants.append(variant)

                # Add occurrence
                existing.occurrences.append(NameOccurrence(
                    file=source_file,
                    context=extracted.context
                ))
            else:
                # Create new entry
                aggregated[key] = AggregatedName(
                    name=extracted.name,
                    name_type=extracted.name_type,
                    variants=extracted.variants.copy(),
                    occurrences=[NameOccurrence(
                        file=source_file,
                        context=extracted.context
                    )]
                )

    return aggregated
