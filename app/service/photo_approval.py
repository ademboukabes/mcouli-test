from __future__ import annotations

from uuid import UUID

from app.core.exceptions import AppException
from app.core.logger import logger
from app.service.staged_upload_storage import StagedUploadStorageService
from db.generated import photo_approvals as photo_approval_queries
from db.generated import photos as photo_queries


class PhotoApprovalService:
    def __init__(
        self,
        *,
        photo_approval_querier: photo_approval_queries.AsyncQuerier,
        photo_querier: photo_queries.AsyncQuerier,
        storage_service: StagedUploadStorageService,
    ) -> None:
        self._approval_querier = photo_approval_querier
        self._photo_querier = photo_querier
        self._storage_service = storage_service

    async def decide(
        self,
        *,
        photo_id: UUID,
        user_id: UUID,
        decision: str,
    ) -> str:
        updated = await self._approval_querier.update_photo_approval_decision(
            photo_id=photo_id,
            decision=decision,
            user_id=user_id,
        )
        if updated is None:
            raise AppException.not_found("Photo approval not found")

        approvals = []
        async for a in self._approval_querier.get_photo_approvals_by_photo_id(photo_id=photo_id):
            approvals.append(a)

        pending = [a for a in approvals if a.decision == "pending"]
        if pending:
            return "pending"

        rejected = [a for a in approvals if a.decision == "rejected"]
        if rejected:
            await self._photo_querier.update_photo_status(id=photo_id, status="rejected")
            await self._delete_photo_storage(photo_id)
            return "rejected"

        await self._photo_querier.update_photo_status(id=photo_id, status="approved")
        return "approved"

    async def _delete_photo_storage(self, photo_id: UUID) -> None:
        photo = await self._photo_querier.get_photo_by_id(id=photo_id)
        if photo is None:
            return
        try:
            await self._storage_service.delete_storage_key(photo.storage_key)
            logger.info("Deleted storage for rejected photo %s", photo_id)
        except Exception as exc:
            logger.warning("Failed to delete storage for photo %s: %s", photo_id, exc)
