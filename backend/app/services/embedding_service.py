import asyncio
import hashlib
import logging
import math
import re
from typing import List, Optional
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_deterministic_mock_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Generates a deterministic vector using feature hashing.
    Used ONLY when EMBEDDING_PROVIDER is explicitly set to 'mock' or in unit testing.
    """
    cleaned = text.lower().strip()
    if not cleaned:
        vec = [0.0] * dim
        vec[0] = 1.0
        return vec

    tokens = re.findall(r"\w+", cleaned)
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
    Supports:
    - 'local' / 'sentence-transformers': Local sentence-transformers/all-MiniLM-L6-v2 (384-dim, L2-normalized)
    - 'openai': OpenAI text-embedding-3-small (1536-dim)
    - 'mock': Deterministic feature-hashed vector for testing
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dim: Optional[int] = None,
        provider: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model or settings.EMBEDDING_MODEL
        self.dim = dim or settings.EMBEDDING_DIM
        self.provider = (provider or getattr(settings, "EMBEDDING_PROVIDER", "local")).lower()
        self._client: Optional[AsyncOpenAI] = None
        self._cached_key: Optional[str] = None
        self._local_model = None

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
                        f"Failed to initialize OpenAI client: {exc}."
                    )
                    self._client = None
        else:
            self._client = None
        return self._client

    def _get_local_model(self):
        """Lazy loader for local SentenceTransformer model."""
        if self._local_model is None:
            logger.info(f"Loading local SentenceTransformer model: {self.model}")
            from sentence_transformers import SentenceTransformer
            self._local_model = SentenceTransformer(self.model)
        return self._local_model

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate a single vector embedding."""
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0]

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of text strings using configured provider.
        Never silently falls back to mock when local or OpenAI provider fails.
        """
        if not texts:
            return []

        # 1. Local SentenceTransformer Provider (Default)
        if self.provider in ("local", "sentence-transformers"):
            try:
                local_model = self._get_local_model()
                safe_texts = [t if t.strip() else " " for t in texts]
                raw_embeddings = await asyncio.to_thread(
                    local_model.encode,
                    safe_texts,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )
                embeddings = [e.tolist() for e in raw_embeddings]
                return embeddings
            except Exception as exc:
                logger.error(f"Local sentence-transformers embedding failed: {exc}")
                raise RuntimeError(
                    f"Local embedding generation failed with model '{self.model}': {exc}"
                ) from exc

        # 2. OpenAI Provider
        if self.provider == "openai":
            openai_client = self.client
            if not openai_client:
                raise ValueError("EMBEDDING_PROVIDER is 'openai' but OPENAI_API_KEY is not set.")
            try:
                safe_texts = [t if t.strip() else " " for t in texts]
                response = await openai_client.embeddings.create(
                    input=safe_texts,
                    model=self.model,
                )
                return [item.embedding for item in response.data]
            except Exception as exc:
                logger.error(f"OpenAI embedding API call failed: {exc}")
                raise RuntimeError(f"OpenAI embedding generation failed: {exc}") from exc

        # 3. Explicit Mock Provider
        if self.provider == "mock":
            return [generate_deterministic_mock_embedding(t, dim=self.dim) for t in texts]

        raise ValueError(f"Unknown EMBEDDING_PROVIDER: '{self.provider}'. Supported: 'local', 'openai', 'mock'")


# Global singleton instance
embedding_service = EmbeddingService()
