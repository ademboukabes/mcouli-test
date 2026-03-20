"""Configuration shared between notification providers."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseSettings, Field


class NotificationWorkerSettings(BaseSettings):
    """Environment driven configuration for the notification worker."""

    apn_certificate_path: str = Field(
        "/path/to/certificate.pem", description="Path to the APNs certificate in PEM format"
    )
    apn_use_sandbox: bool = Field(True, description="Whether to speak to the APNs sandbox endpoint")
    apn_use_alternative_port: bool = Field(
        False, description="Use the alternative port when connecting to APNs"
    )
    apn_topic: Optional[str] = Field(
        None, description="APNs topic (i.e. bundle ID) to target"
    )
    webpush_vapid_private_key: Optional[str] = Field(None, description="VAPID private key for web push")
    webpush_vapid_claims_subject: str = Field(
        "mailto:alerts@example.com", description="VAPID subject for push subscriptions"
    )

    class Config:
        env_prefix = "NOTIFICATION_"


settings = NotificationWorkerSettings()
