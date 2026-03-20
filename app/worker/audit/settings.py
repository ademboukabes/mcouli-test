from __future__ import annotations

from pydantic_settings import BaseSettings


class AuditWorkerSettings(BaseSettings):

    
    class Config:
        env_prefix = "AUDIT_"


settings = AuditWorkerSettings() # type: ignore
