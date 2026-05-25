"""OpenAI API integration for text editing."""

import json
import os
from typing import Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APITimeoutError

from .models import Chunk, Correction


SYSTEM_PROMPT_TEMPLATE = """You fix OCR scanning errors only. Nothing else.

{custom_instructions}

Return corrections as JSON:
{{
  "corrections": [
    {{"old": "error text", "new": "corrected text", "reason": "brief explanation"}}
  ]
}}

OCR errors are CHARACTER-LEVEL mistakes from scanning, such as:
- 'rn' misread as 'm' (e.g., "bom" -> "born")
- 'cl' misread as 'd' (e.g., "doud" -> "cloud")
- Missing or extra letters (e.g., "teh" -> "the")
- Wrong punctuation from scanning (e.g., "U.S, A" -> "U.S.A")
- Double spaces

NOT OCR errors (do NOT fix these):
- Word substitutions (e.g., "Thy" -> "Zion") - NEVER change one word to a different word
- Grammar or style issues
- Anything that requires understanding meaning or context
- Proper nouns, place names, personal names - leave these EXACTLY as written

Rules:
- "old" must be MINIMAL (1-5 words max)
- "old" must match text EXACTLY
- Return empty array if no OCR errors: {{"corrections": []}}
- When in doubt, do not suggest a correction"""


class OpenAIEditor:
    """Handles OpenAI API calls for text editing."""

    def __init__(
        self,
        model: str = "gpt-5.4-mini",
        api_key: Optional[str] = None,
        custom_instructions: str = ""
    ):
        self.model = model
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            timeout=60.0  # 60 second timeout
        )
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
                old_text = item["old"]
                new_text = item["new"]

                # Skip no-op corrections where old == new
                if old_text == new_text:
                    continue

                corrections.append(Correction(
                    paragraph_id="",  # No longer used - we search all nodes
                    old_text=old_text,
                    new_text=new_text,
                    reason=item.get("reason", "")
                ))
            except KeyError as e:
                print(f"Warning: Skipping malformed correction (missing {e}): {item}")
                continue

        return corrections
