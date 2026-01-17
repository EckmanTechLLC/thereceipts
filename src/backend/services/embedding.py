"""
Embedding Service for TheReceipts semantic search.

Generates embeddings using OpenAI ada-002 (1536 dimensions) for claim cards
and user queries to enable vector similarity search.
"""

import asyncio
from typing import List, Optional
from openai import AsyncOpenAI, OpenAIError
from config import settings


class EmbeddingServiceError(Exception):
    """Base exception for embedding service errors."""
    pass


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI ada-002.

    Embeddings are 1536-dimensional vectors used for semantic similarity search
    via pgvector's cosine similarity.
    """

    # OpenAI embedding model (1536 dimensions)
    MODEL_NAME = "text-embedding-ada-002"
    EMBEDDING_DIMENSIONS = 1536

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds

    def __init__(self):
        """
        Initialize Embedding Service.

        Raises:
            EmbeddingServiceError: If OpenAI API key not configured
        """
        if not settings.OPENAI_API_KEY:
            raise EmbeddingServiceError("OpenAI API key not configured")

        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.

        Args:
            text: Text to embed (typically a claim question or claim_text)

        Returns:
            List of 1536 floats representing the embedding vector

        Raises:
            EmbeddingServiceError: If embedding generation fails after retries
        """
        if not text or not text.strip():
            raise EmbeddingServiceError("Cannot generate embedding for empty text")

        # Clean and normalize text
        text = text.strip()

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.embeddings.create(
                    model=self.MODEL_NAME,
                    input=text
                )

                embedding = response.data[0].embedding

                # Validate embedding dimensions
                if len(embedding) != self.EMBEDDING_DIMENSIONS:
                    raise EmbeddingServiceError(
                        f"Unexpected embedding dimensions: {len(embedding)} "
                        f"(expected {self.EMBEDDING_DIMENSIONS})"
                    )

                return embedding

            except OpenAIError as e:
                if attempt < self.MAX_RETRIES - 1:
                    # Exponential backoff
                    delay = self.RETRY_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise EmbeddingServiceError(
                        f"Failed to generate embedding after {self.MAX_RETRIES} attempts: {str(e)}"
                    )

            except Exception as e:
                raise EmbeddingServiceError(f"Unexpected error generating embedding: {str(e)}")

    async def batch_generate_embeddings(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts with batching.

        Args:
            texts: List of text strings to embed
            batch_size: Number of texts to process per batch (OpenAI limit: 2048)

        Returns:
            List of embeddings (same order as input texts)
            Returns None for any texts that fail to embed

        Raises:
            EmbeddingServiceError: If batch processing fails critically
        """
        if not texts:
            return []

        embeddings: List[Optional[List[float]]] = []

        # Process in batches to respect API limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Filter out empty strings
            batch_with_indices = [
                (idx, text.strip())
                for idx, text in enumerate(batch)
                if text and text.strip()
            ]

            if not batch_with_indices:
                # All texts in this batch are empty
                embeddings.extend([None] * len(batch))
                continue

            # Extract just the texts for API call
            batch_texts = [text for _, text in batch_with_indices]

            try:
                response = await self.client.embeddings.create(
                    model=self.MODEL_NAME,
                    input=batch_texts
                )

                # Map embeddings back to original positions
                batch_embeddings = [None] * len(batch)
                for api_idx, (original_idx, _) in enumerate(batch_with_indices):
                    embedding = response.data[api_idx].embedding

                    # Validate dimensions
                    if len(embedding) == self.EMBEDDING_DIMENSIONS:
                        batch_embeddings[original_idx] = embedding

                embeddings.extend(batch_embeddings)

            except OpenAIError as e:
                # For batch errors, we could retry failed texts individually
                # For now, just mark this batch as failed
                embeddings.extend([None] * len(batch))
                print(f"Warning: Batch embedding failed for batch {i // batch_size}: {str(e)}")

            except Exception as e:
                embeddings.extend([None] * len(batch))
                print(f"Warning: Unexpected error in batch {i // batch_size}: {str(e)}")

        return embeddings

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two embedding vectors.

        Note: pgvector handles this natively in SQL, but this method is useful
        for testing and validation.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Cosine similarity score (0 to 1, where 1 is identical)

        Raises:
            EmbeddingServiceError: If vectors have different dimensions
        """
        if len(vec1) != len(vec2):
            raise EmbeddingServiceError(
                f"Vector dimension mismatch: {len(vec1)} vs {len(vec2)}"
            )

        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Calculate magnitudes
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Cosine similarity
        return dot_product / (magnitude1 * magnitude2)
