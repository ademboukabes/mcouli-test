from enum import Enum
from typing import Any, Callable, Optional
from nats.aio.client import Client as NATS
from nats.js.client import JetStreamContext
from nats.js.api import DeliverPolicy, AckPolicy, StreamConfig
from nats.js.errors import NotFoundError
from nats.aio.msg import Msg
from pydantic import BaseModel

from app.core.config import settings
from app.core.constant import (
    AUDIT_EVENT_SUBJECT,
    FINAL_BUCKET_CLEANUP_SUBJECT,
    NOTIFICATION_EVENT_SUBJECT,
    UPLOAD_GROUP_IMPORT_SUBJECT,
)
from app.core.logger import logger


class Message(BaseModel):
    data: dict[str, Any]


class NatsSubjects(Enum):
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    NOTIFICATION_EVENT = NOTIFICATION_EVENT_SUBJECT
    AUDIT_EVENT = AUDIT_EVENT_SUBJECT
    STAFF_UPLOAD_GROUP_IMPORT_REQUESTED = UPLOAD_GROUP_IMPORT_SUBJECT
    STAFF_UPLOAD_GROUP_CREATED = "staff.upload_group.created"
    STAFF_UPLOAD_GROUP_APPROVED = "staff.upload_group.approved"
    STAFF_UPLOAD_GROUP_REJECTED = "staff.upload_group.rejected"
    FINAL_BUCKET_CLEANUP = FINAL_BUCKET_CLEANUP_SUBJECT
    STAFF_UPLOAD_REQUEST_CREATED = "staff.upload_request.created"
    STAFF_UPLOAD_REQUEST_APPROVED = "staff.upload_request.approved"
    STAFF_UPLOAD_REQUEST_REJECTED = "staff.upload_request.rejected"
    PHOTO_PROCESS = "photo.process"
    PHOTO_DRIVE_SYNC_REQUESTED = "photo.drive_sync.requested"
    EMAIL_SEND_OTP = "email.send_otp"


SUBJECT_TO_STREAM: dict[str, str] = {
    NatsSubjects.USER_SIGNUP.value: "auth_stream",
    NatsSubjects.USER_LOGIN.value: "auth_stream",
    NatsSubjects.USER_LOGOUT.value: "auth_stream",
    NatsSubjects.NOTIFICATION_EVENT.value: "notification_stream",
    NatsSubjects.AUDIT_EVENT.value: "audit_stream",
    NatsSubjects.STAFF_UPLOAD_GROUP_IMPORT_REQUESTED.value: "upload_group_stream",
    NatsSubjects.STAFF_UPLOAD_GROUP_CREATED.value: "upload_group_stream",
    NatsSubjects.STAFF_UPLOAD_GROUP_APPROVED.value: "upload_group_stream",
    NatsSubjects.STAFF_UPLOAD_GROUP_REJECTED.value: "upload_group_stream",
    NatsSubjects.FINAL_BUCKET_CLEANUP.value: "cleanup_stream",
    NatsSubjects.STAFF_UPLOAD_REQUEST_CREATED.value: "upload_request_stream",
    NatsSubjects.STAFF_UPLOAD_REQUEST_APPROVED.value: "upload_request_stream",
    NatsSubjects.STAFF_UPLOAD_REQUEST_REJECTED.value: "upload_request_stream",
    NatsSubjects.PHOTO_PROCESS.value: "photo_process_stream",
    NatsSubjects.PHOTO_DRIVE_SYNC_REQUESTED.value: "drive_sync_stream",
    NatsSubjects.EMAIL_SEND_OTP.value: "email_stream",
}


class NatsClient:
    _nc: Optional[NATS] = None
    _js: Optional[JetStreamContext] = None

    @staticmethod
    async def connect(
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        if NatsClient._nc is None:
            nc = NATS()
            await nc.connect(
                servers=[f"nats://{host or settings.NATS_HOST}:{port or settings.NATS_PORT}"],
                user=user or settings.NATS_USER,
                password=password or settings.NATS_PASSWORD,
            )
            NatsClient._nc = nc
            NatsClient._js = nc.jetstream()  # type: ignore

    @staticmethod
    async def close() -> None:
        if NatsClient._nc and not NatsClient._nc.is_closed:
            try:
                await NatsClient._nc.drain()
                await NatsClient._nc.close()
            finally:
                NatsClient._nc = None
                NatsClient._js = None

    @staticmethod
    async def publish(subject: NatsSubjects | str, message: bytes) -> None:
        if NatsClient._nc is None:
            await NatsClient.connect()
        nc = NatsClient._nc
        assert nc is not None
        subject_name = subject.value if isinstance(subject, NatsSubjects) else subject
        await nc.publish(subject_name, message)

    @staticmethod
    async def subscribe(subject: NatsSubjects | str, callback: Callable[[Any], Any]) -> None:
        if NatsClient._nc is None:
            await NatsClient.connect()
        nc = NatsClient._nc
        assert nc is not None

        async def _wrapper(msg: Msg) -> None:
            await callback(msg.data)

        subject_name = subject.value if isinstance(subject, NatsSubjects) else subject
        await nc.subscribe(subject_name, cb=_wrapper)  # type: ignore


    @staticmethod
    async def js_publish(subject: NatsSubjects | str, message: bytes, stream_name: str | None = None) -> None:
        if NatsClient._js is None:
            await NatsClient.connect()
        js = NatsClient._js
        assert js is not None
        subject_name = subject.value if isinstance(subject, NatsSubjects) else subject
        resolved_stream = stream_name or SUBJECT_TO_STREAM.get(subject_name)
        if resolved_stream is None:
            logger.warning(f"No stream mapped for subject {subject_name}, but js_publish was called.")
            return await NatsClient.publish(subject, message)
            
        await NatsClient.ensure_stream(stream_name=resolved_stream, subjects=[subject_name])
        await js.publish(subject_name, message, stream=resolved_stream)

    @staticmethod
    async def js_subscribe(
        subject: NatsSubjects | str,
        callback: Callable[[Any], Any],
        stream_name: str | None = None,
        durable_name: str | None = None,
        ack_policy: AckPolicy = AckPolicy.EXPLICIT
    ) -> None:
        if NatsClient._js is None:
            await NatsClient.connect()

        subject_name = subject.value if isinstance(subject, NatsSubjects) else subject
        resolved_stream = stream_name or SUBJECT_TO_STREAM.get(subject_name)
        if not resolved_stream:
            raise ValueError(f"Cannot js_subscribe to {subject_name}: no stream mapped.")
            
        resolved_durable = durable_name or f"{resolved_stream}_consumer"

        await NatsClient.ensure_stream(stream_name=resolved_stream, subjects=[subject_name])

        async def _wrapper(msg: Msg) -> None:
            try:
                await callback(msg.data)
                await msg.ack()
            except Exception as exc:
                logger.error(f"Error processing message from {subject_name}, NACKing: {exc}")
                await msg.nak()
                raise
                
        js = NatsClient._js
        assert js is not None
        await js.subscribe(
            subject=subject_name,
            stream=resolved_stream,
            durable=resolved_durable,
            cb=_wrapper,
            deliver_policy=DeliverPolicy.NEW,
            # ack_policy=ack_policy
        )

    @staticmethod
    async def ensure_stream(*, stream_name: str, subjects: list[str]) -> None:
        if NatsClient._js is None:
            await NatsClient.connect()
        js = NatsClient._js
        assert js is not None
        try:
            await js.stream_info(stream_name)
        except NotFoundError:
            await js.add_stream( # type: ignore
                name=stream_name,
                config=StreamConfig(
                    name=stream_name,
                    subjects=subjects,
                ),
            )
