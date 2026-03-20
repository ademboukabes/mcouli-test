"""Audit worker that stores security-relevant events emitted over NATS."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import sqlalchemy.ext.asyncio
from pydantic import ValidationError

from app.core.constant import AUDIT_EVENT_SUBJECT
from app.core.logger import logger
from app.infra.database import engine
from app.infra.nats import NatsClient, NatsSubjects
from app.service.audit import AuditService
from db.generated import audit as audit_queries

from app.worker.audit.schema import AuditEventMessage
from app.worker.audit.settings import settings


async def init_worker() -> None:
    logger.info("Audit worker starting with metadata limit %s", settings.max_metadata_entries)


class AuditDeliveryWorker:
    def __init__(self) -> None:
        self._conn: sqlalchemy.ext.asyncio.AsyncConnection | None = None
        self._audit_service: AuditService | None = None

    async def start(self) -> None:
        if self._conn is not None:
            return
        self._conn = await engine.connect()
        self._audit_service = AuditService(audit_queries.AsyncQuerier(self._conn))

    async def stop(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._audit_service = None

    async def persist(self, payload: AuditEventMessage) -> None:
        if self._audit_service is None:
            logger.warning("Audit service is unavailable for %s", payload.event_type)
            return
        metadata = self._prune_metadata(payload.metadata)
        await self._audit_service.record_event(
            event_type=payload.event_type,
            user_id=payload.user_id,
            metadata=metadata,
        )
        logger.info("Persisted audit %s for %s", payload.event_type, payload.user_id)

    @staticmethod
    def _prune_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
        if not metadata:
            return metadata
        if len(metadata) <= settings.max_metadata_entries:
            return metadata
        trimmed = {}
        for idx, key in enumerate(list(metadata)):
            if idx >= settings.max_metadata_entries:
                break
            trimmed[key] = metadata[key]
        logger.warning("Trimmed audit metadata to %s entries", settings.max_metadata_entries)
        return trimmed


def _parse_payload(raw_data: bytes) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_data.decode("utf-8"))
        if not isinstance(parsed, dict):
            logger.warning("Audit payload must be an object, got %s", type(parsed))
            return None
        return parsed
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Cannot parse audit payload: %s", exc)
        return None


async def _handle_event(worker: AuditDeliveryWorker, raw_data: bytes) -> None:
    parsed = _parse_payload(raw_data)
    if parsed is None:
        return
    try:
        payload = AuditEventMessage.parse_obj(parsed)
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
    await worker.start()
    await NatsClient.connect()
    try:
        await listen_nats_event(worker)
        await asyncio.Event().wait()
    finally:
        await worker.stop()
        await NatsClient.close()


if __name__ == "__main__":
    asyncio.run(main())
