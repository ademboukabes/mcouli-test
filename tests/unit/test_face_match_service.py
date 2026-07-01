"""
Unit tests for SingleFaceMatchService.

All database and service collaborators are mocked — no live infrastructure required.
Tests cover all decision branches: auto-approve, threshold rejection, happy-path match,
idempotency guards, and notification side-effects.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.service.face_match import SingleFaceMatchService
from app.schema.internal.single_face_match import BBoxPayload, SingleFaceMatchJob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def photo_face_querier() -> AsyncMock:
    from db.generated import photo_faces as pf_queries
    q = MagicMock(spec=pf_queries.AsyncQuerier)
    q.photo_faces_photo_exists = AsyncMock(return_value=object())  # truthy → photo exists
    q.photo_faces_match_exists_for_photo = AsyncMock(return_value=None)  # no duplicate
    q.photo_faces_ensure_face_match = AsyncMock()
    return q


@pytest.fixture
def photo_querier() -> AsyncMock:
    from db.generated import photos as photo_queries
    q = MagicMock(spec=photo_queries.AsyncQuerier)
    q.update_photo_status = AsyncMock(return_value=None)
    return q


@pytest.fixture
def user_match_service() -> AsyncMock:
    from app.service.users import AuthService
    svc = MagicMock(spec=AuthService)
    svc.find_closest_user = AsyncMock()
    return svc


@pytest.fixture
def notification_service() -> AsyncMock:
    from app.service.user_notification import UserNotificationService
    svc = MagicMock(spec=UserNotificationService)
    svc.create_notification = AsyncMock()
    return svc


@pytest.fixture
def service(
    photo_face_querier: AsyncMock,
    photo_querier: AsyncMock,
    user_match_service: AsyncMock,
    notification_service: AsyncMock,
) -> SingleFaceMatchService:
    return SingleFaceMatchService(
        conn=MagicMock(),
        photo_face_querier=photo_face_querier,
        photo_querier=photo_querier,
        user_match_service=user_match_service,
        user_notification_service=notification_service,
    )


@pytest.fixture
def job() -> SingleFaceMatchJob:
    return SingleFaceMatchJob(
        photo_id=uuid.uuid4(),
        image_ref="photos/test.jpg",
        face_index=0,
    )


@pytest.fixture
def bbox() -> BBoxPayload:
    return BBoxPayload(x1=10.0, y1=20.0, x2=100.0, y2=200.0)


def _make_embedding(value: float = 0.5) -> list[float]:
    return [value] * 512


def _closest_match(distance: float = 0.3) -> object:
    from app.schema.internal.single_face_match import ClosestUserMatch
    return ClosestUserMatch(user_id=uuid.uuid4(), distance=distance)


# ===========================================================================
# 1. Auto-approve — no enrolled users in DB
# ===========================================================================


class TestAutoApproveNoUsers:
    @pytest.mark.asyncio
    async def test_photo_approved_when_no_users(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_querier: AsyncMock,
        user_match_service: AsyncMock,
    ) -> None:
        user_match_service.find_closest_user.return_value = None  # empty DB

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        photo_querier.update_photo_status.assert_called_once_with(
            id=job.photo_id, status="approved"
        )

    @pytest.mark.asyncio
    async def test_no_notification_when_auto_approved(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        user_match_service: AsyncMock,
        notification_service: AsyncMock,
    ) -> None:
        user_match_service.find_closest_user.return_value = None

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        notification_service.create_notification.assert_not_called()


# ===========================================================================
# 2. Auto-approve — distance above threshold
# ===========================================================================


class TestAutoApproveDistanceThreshold:
    @pytest.mark.asyncio
    async def test_photo_approved_when_distance_exceeds_threshold(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_querier: AsyncMock,
        user_match_service: AsyncMock,
    ) -> None:
        from app.worker.photo_worker.settings import settings as worker_settings

        # Distance just above the threshold → no match → auto-approve
        bad_match = _closest_match(distance=worker_settings.similarity_threshold + 0.01)
        user_match_service.find_closest_user.return_value = bad_match

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        photo_querier.update_photo_status.assert_called_once_with(
            id=job.photo_id, status="approved"
        )

    @pytest.mark.asyncio
    async def test_no_db_write_when_distance_exceeds_threshold(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        user_match_service: AsyncMock,
    ) -> None:
        from app.worker.photo_worker.settings import settings as worker_settings

        bad_match = _closest_match(distance=worker_settings.similarity_threshold + 0.01)
        user_match_service.find_closest_user.return_value = bad_match

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        photo_face_querier.photo_faces_ensure_face_match.assert_not_called()


# ===========================================================================
# 3. Happy-path match → notification sent
# ===========================================================================


class TestSuccessfulMatch:
    @pytest.mark.asyncio
    async def test_face_match_stored_in_db(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        user_match_service: AsyncMock,
    ) -> None:
        good_match = _closest_match(distance=0.1)
        user_match_service.find_closest_user.return_value = good_match

        face_match_result = MagicMock()
        face_match_result.face_match_id = uuid.uuid4()
        photo_face_querier.photo_faces_ensure_face_match.return_value = face_match_result

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        photo_face_querier.photo_faces_ensure_face_match.assert_called_once()

    @pytest.mark.asyncio
    async def test_photo_status_set_to_approved_on_match(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        photo_querier: AsyncMock,
        user_match_service: AsyncMock,
    ) -> None:
        good_match = _closest_match(distance=0.1)
        user_match_service.find_closest_user.return_value = good_match

        face_match_result = MagicMock()
        face_match_result.face_match_id = uuid.uuid4()
        photo_face_querier.photo_faces_ensure_face_match.return_value = face_match_result

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        photo_querier.update_photo_status.assert_called_once_with(
            id=job.photo_id, status="approved"
        )

    @pytest.mark.asyncio
    async def test_notification_sent_on_successful_match(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        user_match_service: AsyncMock,
        notification_service: AsyncMock,
    ) -> None:
        good_match = _closest_match(distance=0.1)
        user_match_service.find_closest_user.return_value = good_match

        face_match_result = MagicMock()
        face_match_result.face_match_id = uuid.uuid4()
        photo_face_querier.photo_faces_ensure_face_match.return_value = face_match_result

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        notification_service.create_notification.assert_called_once()
        call_kwargs = notification_service.create_notification.call_args.kwargs
        assert call_kwargs["type"] == "face_match"
        assert call_kwargs["user_id"] == good_match.user_id  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_bbox_serialised_as_json(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        user_match_service: AsyncMock,
        bbox: BBoxPayload,
    ) -> None:
        good_match = _closest_match(distance=0.1)
        user_match_service.find_closest_user.return_value = good_match

        face_match_result = MagicMock()
        face_match_result.face_match_id = uuid.uuid4()
        photo_face_querier.photo_faces_ensure_face_match.return_value = face_match_result

        await service.process_detected_face(job, _make_embedding(), bbox=bbox)

        call_args = photo_face_querier.photo_faces_ensure_face_match.call_args
        params = call_args.args[0]
        parsed_bbox = json.loads(params.bbox)
        assert parsed_bbox == {"x1": 10.0, "y1": 20.0, "x2": 100.0, "y2": 200.0}


# ===========================================================================
# 4. Idempotency guards
# ===========================================================================


class TestIdempotencyGuards:
    @pytest.mark.asyncio
    async def test_skips_if_photo_not_found(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        photo_querier: AsyncMock,
    ) -> None:
        photo_face_querier.photo_faces_photo_exists.return_value = None  # not found

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        photo_querier.update_photo_status.assert_not_called()
        photo_face_querier.photo_faces_ensure_face_match.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_if_match_already_exists(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        photo_querier: AsyncMock,
    ) -> None:
        photo_face_querier.photo_faces_match_exists_for_photo.return_value = object()  # exists

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        photo_querier.update_photo_status.assert_not_called()
        photo_face_querier.photo_faces_ensure_face_match.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_if_missing_image_ref(
        self,
        service: SingleFaceMatchService,
        photo_querier: AsyncMock,
    ) -> None:
        job_no_ref = SingleFaceMatchJob(
            photo_id=uuid.uuid4(),
            image_ref="",  # empty
            face_index=0,
        )

        await service.process_detected_face(job_no_ref, _make_embedding(), bbox=None)

        photo_querier.update_photo_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_notification_if_face_match_already_existed(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        user_match_service: AsyncMock,
        notification_service: AsyncMock,
    ) -> None:
        """If ensure_face_match returns a result with face_match_id=None, it means
        the match was already there — no duplicate notification should be sent."""
        good_match = _closest_match(distance=0.1)
        user_match_service.find_closest_user.return_value = good_match

        result_already_existed = MagicMock()
        result_already_existed.face_match_id = None  # already existed
        photo_face_querier.photo_faces_ensure_face_match.return_value = result_already_existed

        await service.process_detected_face(job, _make_embedding(), bbox=None)

        notification_service.create_notification.assert_not_called()


# ===========================================================================
# 5. Resilience — DB errors don't crash the worker
# ===========================================================================


class TestResilience:
    @pytest.mark.asyncio
    async def test_db_error_is_handled_gracefully(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        photo_face_querier: AsyncMock,
        user_match_service: AsyncMock,
        notification_service: AsyncMock,
    ) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        good_match = _closest_match(distance=0.1)
        user_match_service.find_closest_user.return_value = good_match
        photo_face_querier.photo_faces_ensure_face_match.side_effect = SQLAlchemyError("DB down")

        # Should not raise — worker must stay alive
        await service.process_detected_face(job, _make_embedding(), bbox=None)
        notification_service.create_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_memory_error_is_handled_gracefully(
        self,
        service: SingleFaceMatchService,
        job: SingleFaceMatchJob,
        user_match_service: AsyncMock,
    ) -> None:
        user_match_service.find_closest_user.side_effect = MemoryError("OOM")

        # Should not raise
        await service.process_detected_face(job, _make_embedding(), bbox=None)


# ===========================================================================
# 6. Static helpers
# ===========================================================================


class TestStaticHelpers:
    def test_vector_literal_format(self) -> None:
        embedding = [0.1, 0.2, 0.3]
        result = SingleFaceMatchService._vector_literal(embedding)
        assert result == "[0.1, 0.2, 0.3]"

    def test_serialize_bbox_none_returns_none(self) -> None:
        assert SingleFaceMatchService._serialize_bbox(None) is None

    def test_serialize_bbox_valid(self) -> None:
        bbox = BBoxPayload(x1=1.0, y1=2.0, x2=3.0, y2=4.0)
        result = SingleFaceMatchService._serialize_bbox(bbox)
        assert result is not None
        parsed = json.loads(result)
        assert parsed == {"x1": 1.0, "y1": 2.0, "x2": 3.0, "y2": 4.0}
