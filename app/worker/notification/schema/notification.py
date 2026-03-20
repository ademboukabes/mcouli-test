from __future__ import annotations

import dataclasses
import uuid
from typing import Any, Mapping

from app.core.constant import NotificationChannel
from app.core.logger import logger


@dataclasses.dataclass
class NotificationEventPayload:

    user_id: uuid.UUID
    channel: NotificationChannel
    title: str | None = None
    body: str | None = None
    data: dict[str, str] = dataclasses.field(default_factory=dict)
    device_info: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "NotificationEventPayload" | None:
        raw_user_id = payload.get("user_id")
        raw_channel = payload.get("channel")
        if not isinstance(raw_user_id, str) or not isinstance(raw_channel, str):
            logger.warning("Notification payload missing user_id or channel: %s", payload)
            return None
        try:
            user_id = uuid.UUID(raw_user_id)
        except ValueError as exc:
            logger.warning("Invalid user_id %s: %s", raw_user_id, exc)
            return None
        try:
            channel = NotificationChannel(raw_channel)
        except ValueError:
            logger.warning("Unsupported notification channel %s", raw_channel)
            return None

        raw_data = payload.get("data")
        data_dict: dict[str, str] = {}
        if isinstance(raw_data, Mapping):
            data_dict = {str(k): str(v) for k, v in raw_data.items()}

        device_info = payload.get("device_info")
        if device_info is not None and not isinstance(device_info, Mapping):
            logger.warning("device_info must be an object, dropping it: %s", payload)
            device_info = None

        metadata = payload.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            logger.warning("metadata must be an object, dropping it: %s", payload)
            metadata = None

        return cls(
            user_id=user_id,
            channel=channel,
            title=payload.get("title"),
            body=payload.get("body"),
            data=data_dict,
            device_info=device_info,
            metadata=metadata,
        )
