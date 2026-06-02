from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PhotoWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PHOTO_WORKER_")

    stream_name: str = Field("photo_processing")
    durable_name: str = Field("photo_processing_worker")
    similarity_threshold: float = Field(0.5)


settings = PhotoWorkerSettings()  # type: ignore
