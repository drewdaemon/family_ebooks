"""OpenAI API integration for text editing."""

import json
import os
from typing import Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APITimeoutError

from .models import Chunk, Correction


SYSTEM_PROMPT_TEMPLATE = """You are proofreading text from a digitized 1969 family history book.
Look for OCR errors, spelling mistakes, and punctuation issues.

{custom_instructions}

Return corrections in this JSON format:
{{
  "corrections": [
    {{"p": "paragraph_id", "old": "error text", "new": "corrected text", "reason": "brief explanation"}}
  ]
}}

Rules:
- Only return actual errors, not stylistic preferences
- "p" is the paragraph ID (shown in brackets like [filename_p001])
- "old" must match text exactly as it appears (including capitalization)
- Return empty array if no corrections needed: {{"corrections": []}}
- Do not change formatting, line breaks, or spacing unless clearly wrong
- Preserve all names, places, and dates as-is unless obviously misspelled
- Focus on: typos, OCR errors (like 'rn' misread as 'm'), missing/extra letters"""


class OpenAIEditor:
    """Handles OpenAI API calls for text editing."""

    def __init__(
        self,
        model: str = "gpt-5.4-nano",
        api_key: Optional[str] = None,
        custom_instructions: str = ""
    ):
        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.custom_instructions = custom_instructions
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            custom_instructions=custom_instructions
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError))
    )
    def process_chunk(self, chunk: Chunk) -> list[Correction]:
        """Send a chunk to OpenAI for editing and parse the response.

        Args:
            chunk: The Chunk object containing text nodes to edit

        Returns:
            List of Correction objects extracted from the response
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": chunk.combined_text}
            ],
            temperature=0.1,  # Low temperature for consistent corrections
            response_format={"type": "json_object"}
        )

        return self.parse_response(response.choices[0].message.content)

    def parse_response(self, response_text: str) -> list[Correction]:
        """Parse the JSON response from OpenAI into Correction objects.

        Args:
            response_text: The raw JSON string from the API

        Returns:
            List of Correction objects
        """
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse JSON response: {e}")
            return []

        corrections = []
        for item in data.get("corrections", []):
            try:
                corrections.append(Correction(
                    paragraph_id=item["p"],
                    old_text=item["old"],
                    new_text=item["new"],
                    reason=item.get("reason", "")
                ))
            except KeyError as e:
                print(f"Warning: Skipping malformed correction (missing {e}): {item}")
                continue

        return corrections
