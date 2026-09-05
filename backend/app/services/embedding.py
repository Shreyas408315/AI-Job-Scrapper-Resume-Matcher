"""Gemini embedding service."""

from google import genai
from google.genai import types

from app.config import get_settings


async def generate_embedding(text: str) -> list[float]:
    """
    Generate a vector embedding for the given text.

    Args:
        text (str): The text to embed (e.g., extracted resume text or job description)

    Returns:
        list[float]: A list of floats representing the embedding vector.
    """
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
      raise RuntimeError("Gemini provider is not configured")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
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
