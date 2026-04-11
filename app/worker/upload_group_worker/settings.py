from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constant import (
    UPLOAD_GROUP_IMPORT_DURABLE_NAME,
    UPLOAD_GROUP_IMPORT_STREAM,
    UPLOAD_GROUP_IMPORT_SUBJECT,
)
from app.infra.nats import NatsSubjects


class UploadGroupWorkerSettings(BaseSettings):
    subject: str = Field(UPLOAD_GROUP_IMPORT_SUBJECT)
    stream_name: str = Field(UPLOAD_GROUP_IMPORT_STREAM)
    durable_name: str = Field(UPLOAD_GROUP_IMPORT_DURABLE_NAME)

    model_config = SettingsConfigDict(env_prefix="UPLOAD_GROUP_WORKER_")

    @property
    def subject_enum(self) -> NatsSubjects:
        try:
            return NatsSubjects(self.subject)
        except ValueError:
            return NatsSubjects.STAFF_UPLOAD_GROUP_IMPORT_REQUESTED


settings = UploadGroupWorkerSettings()  # type: ignore[call-arg]
