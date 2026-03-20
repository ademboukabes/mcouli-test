"""Configuration for the audit worker."""
from __future__ import annotations

from pydantic import BaseSettings, Field


class AuditWorkerSettings(BaseSettings):
    """Basic feature flags for the audit worker."""

    max_metadata_entries: int = Field(
        40,
        description="Max number of metadata keys kept when persisting audit entries",
        ge=1,
        le=200,
    )

    class Config:
        env_prefix = "AUDIT_"


settings = AuditWorkerSettings()
