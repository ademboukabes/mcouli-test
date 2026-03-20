"""Payload definitions shared across the notification worker."""
from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, root_validator

from app.core.constant import NotificationChannel


class MobileDeviceInfo(BaseModel):
    fcm_token: str | None = None
    apn_token: str | None = None
    platform: str | None = None


class WebPushSubscription(BaseModel):
    endpoint: str
    keys: dict[str, str]
    expiration_time: int | None = None


class NotificationEventPayload(BaseModel):
    user_id: UUID
    channel: NotificationChannel
    title: str | None = None
    body: str | None = None
    data: dict[str, str] = Field(default_factory=dict)
    mobile_device_info: MobileDeviceInfo | None = None
    web_subscription: WebPushSubscription | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(extra="ignore")

    @root_validator(pre=True)
    def _normalize_payload(cls, values: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(values)
        raw_data = normalized.get("data")
        if isinstance(raw_data, Mapping):
            normalized["data"] = {
                key: value
                for key, value in raw_data.items()
                if isinstance(value, str)
            }
        raw_metadata = normalized.get("metadata")
        if isinstance(raw_metadata, Mapping):
            normalized["metadata"] = dict(raw_metadata)
        raw_device_info = normalized.pop("device_info", None)
        if isinstance(raw_device_info, Mapping):
            normalized["mobile_device_info"] = dict(raw_device_info)
        raw_subscription = normalized.pop("subscription", None)
        if isinstance(raw_subscription, Mapping):
            normalized["web_subscription"] = dict(raw_subscription)
        return normalized
