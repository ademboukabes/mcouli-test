from __future__ import annotations

from pydantic import  Field
from pydantic_settings import BaseSettings


class AuditWorkerSettings(BaseSettings):

    max_metadata_entries: int = Field(
        40,
        ge=1,
        le=200,
    )

    class Config:
        env_prefix = "AUDIT_"


settings = AuditWorkerSettings() # type: ignore
