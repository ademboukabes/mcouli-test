from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class PhotoWorkerSettings(BaseSettings):
    stream_name: str = Field("photo_processing")
    durable_name: str = Field("photo_processing_worker")
    similarity_threshold: float = Field(0.5)

    class Config:
        env_prefix = "PHOTO_WORKER_"


settings = PhotoWorkerSettings()  # type: ignore
