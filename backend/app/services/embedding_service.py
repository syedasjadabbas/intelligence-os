import hashlib
import logging
import math
import re
from typing import List, Optional
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_deterministic_mock_embedding(text: str, dim: int = 1536) -> List[float]:
    """
    Generates a deterministic 1536-dimensional L2-normalized vector using feature hashing.
    Preserves semantic similarity based on shared vocabulary and character n-grams.
    Used when OPENAI_API_KEY is omitted or in testing environments.
    """
    cleaned = text.lower().strip()
    if not cleaned:
        vec = [0.0] * dim
        vec[0] = 1.0
        return vec

    tokens = re.findall(r"\w+", cleaned)
    # Extract 3-gram and 4-gram character shingles for subword matching
    shingles = [cleaned[i : i + 4] for i in range(max(0, len(cleaned) - 3))]
    features = tokens + shingles[:60]

    vector = [0.0] * dim

    for feature in features:
        h = hashlib.sha256(feature.encode("utf-8")).digest()
        idx1 = int.from_bytes(h[0:2], "big") % dim
        idx2 = int.from_bytes(h[2:4], "big") % dim
        idx3 = int.from_bytes(h[4:6], "big") % dim
        sign1 = 1.0 if h[6] % 2 == 0 else -1.0
        sign2 = 1.0 if h[7] % 2 == 0 else -1.0
        sign3 = 1.0 if h[8] % 2 == 0 else -1.0

        vector[idx1] += sign1
        vector[idx2] += sign2
        vector[idx3] += sign3

    # L2 Normalization (unit vector)
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        return [round(v / norm, 6) for v in vector]
    else:
        vector[0] = 1.0
        return vector


class EmbeddingService:
    """
    Asynchronous vector embedding service.
    Integrates with OpenAI's text-embedding-3-small API with seamless fallback
    to deterministic feature-hashed embeddings when API keys are not provided.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dim: Optional[int] = None,
    ):
        self.api_key = api_key
        self.model = model or settings.EMBEDDING_MODEL
        self.dim = dim or settings.EMBEDDING_DIM
        self._client: Optional[AsyncOpenAI] = None
        self._cached_key: Optional[str] = None

    @property
    def client(self) -> Optional[AsyncOpenAI]:
        current_key = self.api_key or settings.OPENAI_API_KEY
        if current_key and current_key.strip():
            if self._client is None or self._cached_key != current_key:
                try:
                    self._client = AsyncOpenAI(api_key=current_key.strip())
                    self._cached_key = current_key
                except Exception as exc:
                    logger.warning(
                        f"Failed to initialize OpenAI client: {exc}. Using deterministic mock."
                    )
                    self._client = None
        else:
            self._client = None
        return self._client

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate a single 1536-dimensional vector embedding."""
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0]

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of text strings.
        Dispatches to OpenAI if API client is configured, otherwise uses deterministic mock.
        """
        if not texts:
            return []

        # Use OpenAI if configured
        openai_client = self.client
        if openai_client:
            try:
                # Sanitize inputs (OpenAI cannot take empty strings)
                safe_texts = [t if t.strip() else " " for t in texts]
                response = await self._client.embeddings.create(
                    input=safe_texts,
                    model=self.model,
                )
                return [item.embedding for item in response.data]
            except Exception as exc:
                logger.error(
                    f"OpenAI embedding API call failed: {exc}. Falling back to deterministic embeddings."
                )

        # Fallback generator
        return [generate_deterministic_mock_embedding(t, dim=self.dim) for t in texts]


# Global singleton instance
embedding_service = EmbeddingService()
