from functools import lru_cache

from app.service.face_embedding import FaceEmbeddingService


@lru_cache(maxsize=1)
def get_face_embedding_service() -> FaceEmbeddingService:
    """Return a cached FaceEmbeddingService instance warmed up for the process."""

    return FaceEmbeddingService()
