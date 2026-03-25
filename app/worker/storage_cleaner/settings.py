from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.constant import (
    FINAL_BUCKET_CLEANUP_DURABLE_NAME,
    FINAL_BUCKET_CLEANUP_STREAM,
    FINAL_BUCKET_CLEANUP_SUBJECT,
)
from app.infra.nats import NatsSubjects


class StorageCleanerSettings(BaseSettings):
    subject: str = Field(FINAL_BUCKET_CLEANUP_SUBJECT)
    stream_name: str = Field(FINAL_BUCKET_CLEANUP_STREAM)
    durable_name: str = Field(FINAL_BUCKET_CLEANUP_DURABLE_NAME)
    WINDOW_DAYS = 7

    class Config:
        env_prefix = "STORAGE_CLEANER_"

    @property
    def subject_enum(self) -> NatsSubjects:
        try:
            return NatsSubjects(self.subject)
        except ValueError:
            return NatsSubjects.FINAL_BUCKET_CLEANUP


settings = StorageCleanerSettings()  # type: ignore
