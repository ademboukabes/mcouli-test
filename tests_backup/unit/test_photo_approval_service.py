"""
Unit tests for PhotoApprovalService.

All queriers and the storage service are mocked — no live infrastructure.
Tests cover: approve/reject/pending decision logic, storage cleanup on rejection,
audit logging, and error resilience.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.exceptions import HTTPException

from app.service.photo_approval import PhotoApprovalService
from app.core.constant import AuditEventType


# ---------------------------------------------------------------------------
# Minimal stubs for DB models
# ---------------------------------------------------------------------------


def _make_approval(decision: str, user_id: uuid.UUID | None = None) -> MagicMock:
    a = MagicMock()
    a.decision = decision
    a.user_id = user_id or uuid.uuid4()
    return a


def _make_photo(storage_key: str = "photos/test.jpg") -> MagicMock:
    p = MagicMock()
    p.storage_key = storage_key
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def approval_querier() -> AsyncMock:
    from db.generated import photo_approvals as pa_queries
    q = MagicMock(spec=pa_queries.AsyncQuerier)
    q.update_photo_approval_decision = AsyncMock()
    q.get_photo_approvals_by_photo_id = MagicMock()  # async generator
    return q


@pytest.fixture
def photo_querier() -> AsyncMock:
    from db.generated import photos as photo_queries
    q = MagicMock(spec=photo_queries.AsyncQuerier)
    q.update_photo_status = AsyncMock(return_value=None)
    q.get_photo_by_id = AsyncMock(return_value=_make_photo())
    return q


@pytest.fixture
def storage_service() -> AsyncMock:
    from app.service.staged_upload_storage import StagedUploadStorageService
    svc = MagicMock(spec=StagedUploadStorageService)
    svc.delete_storage_key = AsyncMock()
    return svc


@pytest.fixture
def audit_service() -> AsyncMock:
    from app.service.audit import AuditService
    svc = MagicMock(spec=AuditService)
    svc.create_record = AsyncMock()
    return svc


def _make_service(
    approval_querier: AsyncMock,
    photo_querier: AsyncMock,
    storage_service: AsyncMock,
    audit_service: AsyncMock | None = None,
) -> PhotoApprovalService:
    return PhotoApprovalService(
        photo_approval_querier=approval_querier,
        photo_querier=photo_querier,
        storage_service=storage_service,
        audit_service=audit_service,
    )


def _mock_async_iter(items: list[object]):  # type: ignore[type-arg]
    """Return a MagicMock that behaves like an async for loop."""
    async def _gen():  # type: ignore[return]
        for item in items:
            yield item
    return _gen()


# ===========================================================================
# 1. All decisions == "approved" → photo status becomes "approved"
# ===========================================================================


class TestApproveDecision:
    @pytest.mark.asyncio
    async def test_all_approved_sets_photo_status(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        approvals = [_make_approval("approved"), _make_approval("approved")]

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)

        service = _make_service(approval_querier, photo_querier, storage_service)
        result = await service.decide(photo_id=photo_id, user_id=user_id, decision="approved")

        assert result == "approved"
        photo_querier.update_photo_status.assert_called_once_with(
            id=photo_id, status="approved"
        )

    @pytest.mark.asyncio
    async def test_all_approved_does_not_delete_storage(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        approvals = [_make_approval("approved")]

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)

        service = _make_service(approval_querier, photo_querier, storage_service)
        await service.decide(photo_id=photo_id, user_id=user_id, decision="approved")

        storage_service.delete_storage_key.assert_not_called()


# ===========================================================================
# 2. One rejection → photo status becomes "rejected" + storage deleted
# ===========================================================================


class TestRejectDecision:
    @pytest.mark.asyncio
    async def test_one_rejection_sets_photo_status_rejected(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        approvals = [_make_approval("approved"), _make_approval("rejected")]

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)

        service = _make_service(approval_querier, photo_querier, storage_service)
        result = await service.decide(photo_id=photo_id, user_id=user_id, decision="rejected")

        assert result == "rejected"
        photo_querier.update_photo_status.assert_called_once_with(
            id=photo_id, status="rejected"
        )

    @pytest.mark.asyncio
    async def test_rejection_triggers_storage_deletion(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        approvals = [_make_approval("rejected")]
        storage_key = "photos/reject-me.jpg"
        photo_querier.get_photo_by_id.return_value = _make_photo(storage_key=storage_key)

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)

        service = _make_service(approval_querier, photo_querier, storage_service)
        await service.decide(photo_id=photo_id, user_id=user_id, decision="rejected")

        storage_service.delete_storage_key.assert_called_once_with(storage_key)

    @pytest.mark.asyncio
    async def test_storage_deletion_failure_does_not_raise(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        """Storage errors must be swallowed — they should not surface to the client."""
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        approvals = [_make_approval("rejected")]

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)
        storage_service.delete_storage_key.side_effect = Exception("MinIO unavailable")

        service = _make_service(approval_querier, photo_querier, storage_service)
        # Must not raise despite MinIO being unavailable
        result = await service.decide(photo_id=photo_id, user_id=user_id, decision="rejected")
        assert result == "rejected"


# ===========================================================================
# 3. Pending approvals → returns "pending", no status update
# ===========================================================================


class TestPendingDecision:
    @pytest.mark.asyncio
    async def test_pending_approval_returns_pending(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        approvals = [_make_approval("approved"), _make_approval("pending")]

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)

        service = _make_service(approval_querier, photo_querier, storage_service)
        result = await service.decide(photo_id=photo_id, user_id=user_id, decision="approved")

        assert result == "pending"

    @pytest.mark.asyncio
    async def test_pending_does_not_update_photo_status(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        approvals = [_make_approval("pending"), _make_approval("pending")]

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)

        service = _make_service(approval_querier, photo_querier, storage_service)
        await service.decide(photo_id=photo_id, user_id=user_id, decision="approved")

        photo_querier.update_photo_status.assert_not_called()


# ===========================================================================
# 4. Not found → raises 404
# ===========================================================================


class TestNotFound:
    @pytest.mark.asyncio
    async def test_not_found_raises_404(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        photo_id = uuid.uuid4()
        approval_querier.update_photo_approval_decision.return_value = None  # not found

        service = _make_service(approval_querier, photo_querier, storage_service)
        with pytest.raises(HTTPException) as exc_info:
            await service.decide(
                photo_id=photo_id, user_id=uuid.uuid4(), decision="approved"
            )
        assert exc_info.value.status_code == 404


# ===========================================================================
# 5. Audit logging
# ===========================================================================


class TestAuditLogging:
    @pytest.mark.asyncio
    async def test_audit_called_with_correct_event_type(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
        audit_service: AsyncMock,
    ) -> None:
        photo_id = uuid.uuid4()
        user_id = uuid.uuid4()
        approvals = [_make_approval("approved")]

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)

        service = _make_service(approval_querier, photo_querier, storage_service, audit_service)
        await service.decide(photo_id=photo_id, user_id=user_id, decision="approved")

        audit_service.create_record.assert_called_once()
        call_kwargs = audit_service.create_record.call_args.kwargs
        assert call_kwargs["event_type"] == AuditEventType.PHOTO_APPROVAL_DECIDED
        assert call_kwargs["user_id"] == user_id
        assert str(photo_id) in str(call_kwargs["metadata"])

    @pytest.mark.asyncio
    async def test_no_audit_without_audit_service(
        self,
        approval_querier: AsyncMock,
        photo_querier: AsyncMock,
        storage_service: AsyncMock,
    ) -> None:
        """When audit_service=None, no error must be raised."""
        photo_id = uuid.uuid4()
        approvals = [_make_approval("approved")]

        approval_querier.update_photo_approval_decision.return_value = MagicMock()
        approval_querier.get_photo_approvals_by_photo_id.return_value = _mock_async_iter(approvals)

        # No audit_service passed → audit_service=None
        service = _make_service(approval_querier, photo_querier, storage_service, audit_service=None)
        await service.decide(photo_id=photo_id, user_id=uuid.uuid4(), decision="approved")
        # no assertion needed — just must not raise
