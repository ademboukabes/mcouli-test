from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.logger import logger
from app.schema.internal.single_face_match import BBoxPayload, ClosestUserMatch, SingleFaceMatchJob
from app.service.user_notification import UserNotificationService
from app.service.users import AuthService
from db.generated import photo_faces as photo_face_queries
from db.generated import photos as photo_queries


class SingleFaceMatchService:
    def __init__(
        self,
        *,
        conn: AsyncConnection,
        photo_face_querier: photo_face_queries.AsyncQuerier,
        photo_querier: photo_queries.AsyncQuerier,
        user_match_service: AuthService,
        user_notification_service: UserNotificationService,
    ) -> None:
        self.conn = conn
        self.photo_face_querier = photo_face_querier
        self.photo_querier = photo_querier
        self.user_match_service = user_match_service
        self.user_notification_service = user_notification_service

    async def process_detected_face(
        self,
        job: SingleFaceMatchJob,
        embedding: list[float],
        bbox: BBoxPayload | None,
    ) -> None:  # noqa: C901
        if not job.image_ref:
            logger.warning("Missing image_ref in event payload for photo %s", job.photo_id)
            return

        embedding_literal = self._vector_literal(embedding)
        bbox_payload = self._serialize_bbox(bbox)

        created_face_match_id: UUID | None = None
        matched_user: ClosestUserMatch | None = None

        try:
            async with self.conn.begin():
                if not await self.Check_photo_exists(job.photo_id):
                    logger.warning("Photo not found: %s", job.photo_id)
                    return

                if await self._match_exists_for_photo(job.photo_id):
                    logger.info("Photo %s already matched; skipping", job.photo_id)
                    return

                matched_user = await self.user_match_service.find_closest_user(
                    embedding_literal=embedding_literal,
                )
                if matched_user is None:
                    logger.info("No user embeddings available for matching")
                    return

                from app.worker.photo_worker.settings import settings as worker_settings
                if matched_user.distance > worker_settings.similarity_threshold:
                    logger.info(
                        "Closest user distance %.4f exceeds threshold %.4f for photo %s; skipping",
                        matched_user.distance, worker_settings.similarity_threshold, job.photo_id,
                    )
                    return

                params = photo_face_queries.PhotoFacesEnsureFaceMatchParams(
                    photo_id=job.photo_id,
                    face_index=job.face_index,
                    column_3=embedding_literal,
                    bbox=bbox_payload,
                    user_id=matched_user.user_id,
                    confidence=matched_user.distance,
                )
                result = await self.photo_face_querier.photo_faces_ensure_face_match(params)
                if result is None:
                    logger.warning("Failed to ensure face match for photo %s", job.photo_id)
                    return

                if result.face_match_id is None:
                    logger.info("Match already exists for photo %s; skipping", job.photo_id)
                else:
                    created_face_match_id = result.face_match_id
                    logger.info(
                        "Inserted face match %s for photo %s",
                        created_face_match_id,
                        job.photo_id,
                    )
        except (DBAPIError, SQLAlchemyError) as exc:
            logger.warning("DB write failed for photo %s: %s", job.photo_id, exc)
            return
        except MemoryError:
            logger.error("Out of memory while matching photo %s", job.photo_id)
            return

        if created_face_match_id:
            await self.photo_querier.update_photo_status(
                id=job.photo_id, status="approved",
            )
            await self.user_notification_service.create_notification(
                user_id=matched_user.user_id,
                type="face_match",
                payload={
                    "photo_id": str(job.photo_id),
                },
            )

    async def Check_photo_exists(self, photo_id: UUID) -> bool:
        row = await self.photo_face_querier.photo_faces_photo_exists(id=photo_id)
        return row is not None

    async def _match_exists_for_photo(self, photo_id: UUID) -> bool:
        row = await self.photo_face_querier.photo_faces_match_exists_for_photo(
            photo_id=photo_id,
        )
        return row is not None

    @staticmethod
    def _vector_literal(embedding: list[float]) -> str:
        return "[" + ", ".join(str(x) for x in embedding) + "]"

    @staticmethod
    def _serialize_bbox(bbox: BBoxPayload | None) -> str | None:
        if bbox is None:
            return None
        return json.dumps(
            {"x1": bbox.x1, "y1": bbox.y1, "x2": bbox.x2, "y2": bbox.y2}
        )
