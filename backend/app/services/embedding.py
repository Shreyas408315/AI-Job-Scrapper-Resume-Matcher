"""
Embedding service — calls LLM APIs to generate vector embeddings from text.

DESIGN DECISIONS:
- We use the async OpenAI client because FastAPI is async. Synchronous HTTP
  calls would block the event loop.
- The embedding dimension must match the VECTOR_DIMENSIONS in our pgvector
  columns (1536 for text-embedding-3-small).

WHY ABSTRACTED:
- In the future, you might want to switch to a cheaper/local embedding model
  (like BAAI/bge-small-en). Keeping the embedding logic behind a clean function
  makes that swap easy without touching the router or database logic.
"""

from openai import AsyncOpenAI

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
    
    # We initialize the client inside the function so it picks up
    # the API key if it's set after startup (e.g. during testing).
    # In a larger app, you might inject this client as a dependency.
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    # The API call is async
    response = await client.embeddings.create(
        input=text,
        model=settings.EMBEDDING_MODEL
    )
    
    # Return the float list from the first (and only) result
    return response.data[0].embedding
