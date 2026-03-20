from __future__ import annotations

from typing import Optional

from pydantic import  Field
from pydantic_settings import BaseSettings


class NotificationWorkerSettings(BaseSettings):

    apn_certificate_path: str = Field(
        "/path/to/certificate.pem"
    )
    apn_use_sandbox: bool = Field(True)
    apn_use_alternative_port: bool = Field(
        False
    )
    apn_topic: Optional[str] = Field(
        None
    )
    webpush_vapid_private_key: Optional[str] = Field(None)
    webpush_vapid_claims_subject: str = Field(
        "mailto:alerts@example.com"
    )

    class Config:
        env_prefix = "NOTIFICATION_"


settings = NotificationWorkerSettings() # type: ignore
