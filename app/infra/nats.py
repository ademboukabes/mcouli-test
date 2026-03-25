from enum import Enum
from typing import Any, Callable, Optional
from nats.aio.client import Client as NATS
from nats.js.client import JetStreamContext
from nats.js.api import DeliverPolicy, AckPolicy
from nats.aio.msg import Msg
from pydantic import BaseModel

from app.core.config import settings
from app.core.constant import (
    NOTIFICATION_EVENT_SUBJECT,
    AUDIT_EVENT_SUBJECT,
    FINAL_BUCKET_CLEANUP_SUBJECT,
)


class Message(BaseModel):
    data: dict[str, Any]


class NatsSubjects(Enum):
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    NOTIFICATION_EVENT = NOTIFICATION_EVENT_SUBJECT
    AUDIT_EVENT = AUDIT_EVENT_SUBJECT
    FINAL_BUCKET_CLEANUP = FINAL_BUCKET_CLEANUP_SUBJECT
    STAFF_UPLOAD_REQUEST_CREATED = "staff.upload_request.created"
    STAFF_UPLOAD_REQUEST_APPROVED = "staff.upload_request.approved"
    STAFF_UPLOAD_REQUEST_REJECTED = "staff.upload_request.rejected"

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
            NatsClient._js = nc.jetstream() # type: ignore

    @staticmethod
    async def close() -> None:
        if NatsClient._nc and not NatsClient._nc.is_closed:
            await NatsClient._nc.drain()
            await NatsClient._nc.close()
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
        await nc.subscribe(subject_name, cb=_wrapper) # type: ignore


    @staticmethod
    async def js_publish(subject: NatsSubjects, message: bytes, stream_name: str) -> None:
        if NatsClient._js is None:
            await NatsClient.connect()
        js = NatsClient._js
        assert js is not None
        subject_name = subject.value if isinstance(subject, NatsSubjects) else subject # type: ignore
        await js.publish(subject_name, message, stream=stream_name)

    @staticmethod
    async def js_subscribe(
        subject: NatsSubjects,
        callback: Callable[[Any], Any],
        stream_name: str,
        durable_name: str,
        ack_policy: AckPolicy = AckPolicy.EXPLICIT
    ) -> None:
        if NatsClient._js is None:
            await NatsClient.connect()

        async def _wrapper(msg: Msg) -> None:
            await callback(msg.data)
            await msg.ack()
        js = NatsClient._js
        assert js is not None
        subject_name = subject.value
        await js.subscribe(
            subject=subject_name,
            stream=stream_name,
            durable=durable_name,
            cb=_wrapper,
            deliver_policy=DeliverPolicy.NEW,
            # ack_policy=ack_policy
        )
