import uuid
from typing import Protocol, TypedDict

from app.core.exceptions import AppException, DBException
from db.generated import user as user_queries
from db.generated import user_faces as user_faces_queries


class ImagePayload(TypedDict):
    filename: str | None
    content_type: str | None
    bytes: bytes


class FaceEmbeddingProvider(Protocol):
    async def create_embedding(self, images: list[ImagePayload]) -> str | None:
        """Return a serialized embedding/signature (provider-owned format)."""


class UnconfiguredFaceEmbeddingProvider:
    async def create_embedding(self, images: list[ImagePayload]) -> str | None:
        raise AppException.internal_error("Face embedding provider is not configured")


class EnrollmentService:
    user_querier: user_queries.AsyncQuerier
    user_faces_querier: user_faces_queries.AsyncQuerier
    face_embedding_provider: FaceEmbeddingProvider

    def init(
        self,
        user_querier: user_queries.AsyncQuerier,
        user_faces_querier: user_faces_queries.AsyncQuerier,
        face_embedding_provider: FaceEmbeddingProvider,
    ) -> None:
        self.user_querier = user_querier
        self.user_faces_querier = user_faces_querier
        self.face_embedding_provider = face_embedding_provider

    async def enroll_user_faces(
        self, user_id: uuid.UUID, image_payloads: list[ImagePayload]
    ) -> None:
        # Defensive check: auth dependency should guarantee this already.
        user = await self.user_querier.get_user_by_id(id=user_id)
        if user is None:
            raise AppException.not_found("User not found")

        try:
            existing = await self.user_faces_querier.get_user_face_by_user_id(
                user_id=user_id
            )
            if existing is not None:
                raise AppException.conflict("User is already enrolled")

            embedding = await self.face_embedding_provider.create_embedding(
                image_payloads
            )
            if embedding is None:
                raise AppException.bad_request(
                    "Unable to extract a valid face embedding from provided images"
                )

            created = await self.user_faces_querier.create_user_face(
                user_id=user_id,
                embedding=embedding,
            )
            if created is None:
                raise AppException.internal_error("Failed to persist user face embedding")
        except Exception as exc:
            handled = DBException.handle(exc)
            if handled.status_code != 500:
                raise handled
            raise