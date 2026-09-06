"""Gemini embedding service with exponential backoff.

RESILIENCY:
- LLM providers enforce rate limits (e.g., Gemini returns HTTP 429 when
  we send too many embedding requests in quick succession).
- Without retry logic, syncing a large Greenhouse board (100+ jobs)
  would fail partway through and leave the database in an incomplete state.
- We use exponential backoff with jitter: wait 1s, 2s, 4s, 8s, 16s
  between retries, plus a random component to prevent "thundering herd"
  when multiple requests hit the limit simultaneously.
"""

import asyncio
import logging
import random

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 5
BASE_DELAY_SECONDS = 1.0    # First retry waits ~1 second
MAX_DELAY_SECONDS = 32.0    # Cap the backoff so we don't wait forever
JITTER_RANGE = 0.5          # ±50% randomness on each delay


async def generate_embedding(text: str) -> list[float]:
    """
    Generate a vector embedding for the given text, with automatic retry
    on rate-limit (429) errors.

    Args:
        text: The text to embed (e.g., extracted resume text or job description)

    Returns:
        list[float]: The embedding vector.

    Raises:
        RuntimeError: If Gemini is not configured.
        Exception: If all retry attempts are exhausted.
    """
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("Gemini provider is not configured")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    last_exception = None

    for attempt in range(MAX_RETRIES + 1):  # attempt 0 is the initial try
        try:
            response = await client.aio.models.embed_content(
                model=settings.GEMINI_EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.VECTOR_DIMENSIONS,
                ),
            )
            if not response.embeddings or not response.embeddings[0].values:
                raise ValueError("Gemini returned an empty embedding")
            return list(response.embeddings[0].values)

        except Exception as e:
            last_exception = e
            error_str = str(e).lower()

            # Only retry on rate-limit (429) or transient server errors (500/503)
            is_retryable = (
                "429" in error_str
                or "rate" in error_str
                or "resource_exhausted" in error_str
                or "503" in error_str
                or "overloaded" in error_str
            )

            if not is_retryable or attempt == MAX_RETRIES:
                # Non-retryable error or final attempt — give up
                raise

            # Calculate delay: 1s, 2s, 4s, 8s, 16s (capped at MAX_DELAY_SECONDS)
            delay = min(BASE_DELAY_SECONDS * (2 ** attempt), MAX_DELAY_SECONDS)
            # Add jitter: ±50% randomness
            jitter = delay * random.uniform(-JITTER_RANGE, JITTER_RANGE)
            actual_delay = max(0.1, delay + jitter)

            logger.warning(
                "Embedding rate-limited (attempt %d/%d). "
                "Retrying in %.1fs. Error: %s",
                attempt + 1, MAX_RETRIES, actual_delay, e,
            )
            await asyncio.sleep(actual_delay)

    # Should never reach here, but just in case
    raise last_exception  # type: ignore[misc]

