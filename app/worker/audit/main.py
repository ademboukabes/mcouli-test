import asyncio
import json
from typing import Any
from pydantic import ValidationError
from app.core.constant import AUDIT_EVENT_SUBJECT
from app.core.logger import logger
from app.infra.database import engine
from app.infra.nats import NatsClient, NatsSubjects
from app.service.audit import AuditService
from db.generated import audit as audit_queries
from db.generated import user as user_queries
from app.worker.audit.schema.audit import AuditEventMessage


async def init_worker() -> None:
    logger.info("Audit worker starting with metadata limit ")


class AuditDeliveryWorker:
    async def persist(self, payload: AuditEventMessage) -> None:
        # Fresh connection and transaction per event. engine.begin() commits on
        # success and rolls back on error, with pool_pre_ping revalidating the
        # connection on checkout so a Postgres restart recovers automatically.
        async with engine.begin() as conn:
            service = AuditService(
                audit_queries.AsyncQuerier(conn),
                user_queries.AsyncQuerier(conn),
            )
            await service.record_event(
                event_type=payload.event_type,
                user_id=payload.user_id,
                metadata=payload.metadata,
            )
        logger.info("Persisted audit %s for %s", payload.event_type, payload.user_id)


def _parse_payload(raw_data: bytes) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_data.decode("utf-8"))
        if not isinstance(parsed, dict):
            logger.warning("Audit payload must be an object, got %s", type(parsed)) # type: ignore
            return None
        return parsed # type: ignore
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Cannot parse audit payload: %s", exc)
        return None


async def _handle_event(worker: AuditDeliveryWorker, raw_data: bytes) -> None:
    parsed = _parse_payload(raw_data)
    if parsed is None:
        return
    try:
        payload = AuditEventMessage.model_validate(parsed)
    except ValidationError as exc:
        logger.warning("Audit payload validation failed: %s", exc)
        return
    try:
        await worker.persist(payload)
    except Exception:
        logger.exception("Failed to persist audit for %s", payload.event_type)


async def listen_nats_event(worker: AuditDeliveryWorker) -> None:
    await NatsClient.subscribe(
        NatsSubjects.AUDIT_EVENT,
        lambda data: _handle_event(worker, data),
    )
    logger.info("Listening for audit events on %s", AUDIT_EVENT_SUBJECT)


async def main() -> None:
    await init_worker()
    worker = AuditDeliveryWorker()
    await NatsClient.connect()
    try:
        await listen_nats_event(worker)
        await asyncio.Event().wait()
    finally:
        await NatsClient.close()


if __name__ == "__main__":
    asyncio.run(main())
