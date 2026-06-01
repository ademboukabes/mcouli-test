from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuditWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUDIT_")


settings = AuditWorkerSettings() # type: ignore
