from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple, TypedDict

import cv2 # type: ignore
import numpy as np
from insightface.app import FaceAnalysis  # type: ignore[import-untyped]
from app.core.config import settings
from app.core.exceptions import AppException


BBox = tuple[int, int, int, int]


class FaceImagePayload(TypedDict):
    filename: str
    content_type: str
    bytes: bytes


class FaceStub:
    bbox: Tuple[float, float, float, float]
    det_score: float
    keypoints: List[Tuple[float, float]]
    gender: Optional[Literal["F", "M"]] = None
    age: Optional[int] = None
    embedding: Optional[np.ndarray] = None


@dataclass(frozen=True)
class DetectedFace:
    embedding: list[float]
    bbox: Tuple[float, float, float, float]


class FaceEmbedding:
    def __init__(
        self,
        model_name: str | None = None,
        providers: Sequence[str] | None = None,
        ctx_id: int | None = None,
        det_size: Tuple[int, int] | None = None,
    ) -> None:
        self.model: FaceAnalysis | None = None
        self.model_name = model_name or settings.FACE_EMBEDDING_MODEL_NAME
        if providers is None:
            providers = tuple(
                p.strip()
                for p in settings.FACE_EMBEDDING_PROVIDERS.split(",")
                if p.strip()
            )
        self.providers = providers
        self.ctx_id = settings.FACE_EMBEDDING_CTX_ID if ctx_id is None else ctx_id
        if det_size is None:
            det_size = (
                settings.FACE_EMBEDDING_DET_WIDTH,
                settings.FACE_EMBEDDING_DET_HEIGHT,
            )
        self.det_size = det_size
        self._initialized = False

    def load_model(self) -> None:
        if self.model is not None:
            return

        self.model = FaceAnalysis(
            name=self.model_name,
            providers=list(self.providers),
        )
        print("[FaceEmbedding] model loaded!")

    def init_model(self) -> None:
        if self.model is None:
            raise ValueError("Model not loaded")

        if self._initialized:
            return

        self.model.prepare(ctx_id=self.ctx_id, det_size=self.det_size)  # type: ignore
        self._initialized = True
        print("[FaceEmbedding] model initialized")

    def prepare(self) -> None:
        self.load_model()
        self.init_model()

    def embed(self, image: np.ndarray, bboxes: Sequence[BBox]) -> list[float]:
        if not bboxes:
            raise ValueError("No faces to embed")

        if self.model is None or not self._initialized:
            raise RuntimeError("Model not ready. Call `prepare()` first.")

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        faces: list[FaceStub] = self.model.get(image_rgb)  # type: ignore

        if not faces:
            raise ValueError("No faces detected by the model")

        x1, y1, x2, y2 = bboxes[0] # type: ignore
        target_cx = (x1 + x2) / 2
        target_cy = (y1 + y2) / 2

        best_face: Optional[FaceStub] = None
        best_dist = float("inf")

        for face in faces:
            fx1, fy1, fx2, fy2 = face.bbox
            cx = (fx1 + fx2) / 2
            cy = (fy1 + fy2) / 2

            dist = np.sqrt((cx - target_cx) ** 2 + (cy - target_cy) ** 2)

            if dist < best_dist:
                best_dist = dist
                best_face = face

        if best_face is None or best_face.embedding is None:
            raise ValueError("Failed to generate embedding for selected face")

        embedding = best_face.embedding.flatten()
        return embedding.tolist()


class FaceEmbeddingService:
    def __init__(self, face_embedding: FaceEmbedding | None = None) -> None:
        self.face_embedding = face_embedding or FaceEmbedding()
        self.face_embedding.prepare()

    async def compute_average_embedding(
        self,
        payloads: Sequence[FaceImagePayload],
    ) -> list[float]:
        async def iter_payloads() -> AsyncIterator[FaceImagePayload]:
            for payload in payloads:
                yield payload

        return await self.compute_average_embedding_stream(iter_payloads())

    async def compute_average_embedding_stream(
        self,
        payloads: AsyncIterable[FaceImagePayload],
    ) -> list[float]:

        has_payload = False
        embeddings: list[np.ndarray] = []

        async for payload in payloads:
            has_payload = True
            image = self._decode_image(payload)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Single detection pass — model.get() already returns embeddings
            faces: list[FaceStub] = await asyncio.to_thread(  # type: ignore
                self.face_embedding.model.get, image_rgb  # type: ignore
            )

            if not faces:
                raise AppException.bad_request(
                    f"No faces detected in image {payload['filename']}"
                )

            face = faces[0]

            if face.embedding is None:
                raise AppException.bad_request(
                    f"Failed to generate embedding for {payload['filename']}"
                )

            embeddings.append(face.embedding.astype(np.float32))

        if not has_payload:
            raise AppException.bad_request(
                "At least one image is required for enrollment"
            )

        stacked = np.stack(embeddings, axis=0)
        averaged = np.mean(stacked, axis=0)

        return averaged.astype(float).tolist()

    async def compute_event_embedding(
        self,
        payloads: Sequence[FaceImagePayload],
    ) -> dict[str, list[list[float]]]:

        if not payloads:
            raise AppException.bad_request(
                "At least one image is required"
            )

        results: dict[str, list[list[float]]] = {}

        for payload in payloads:
            try:
                image = self._decode_image(payload)
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

                faces: list[FaceStub] = await asyncio.to_thread( # type: ignore
                    self.face_embedding.model.get, image_rgb  # type: ignore
                )

                results[payload["filename"]] = [
                    face.embedding.flatten().tolist()
                    for face in faces
                    if face.embedding is not None
                ]

            except Exception as e:
                print(f"[FaceEmbeddingService] Skipping {payload['filename']}: {e}")
                results[payload["filename"]] = []

        return results

    async def detect_faces(
        self,
        payload: FaceImagePayload,
    ) -> list[DetectedFace]:
        image = self._decode_image(payload)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        faces: list[FaceStub] = await asyncio.to_thread( # type: ignore
            self.face_embedding.model.get, image_rgb  # type: ignore
        )

        detected: list[DetectedFace] = []
        for face in faces:
            if face.embedding is None:
                continue
            embedding = face.embedding.astype(float).flatten().tolist()
            detected.append(DetectedFace(embedding=embedding, bbox=face.bbox))

        return detected

    def _decode_image(self, payload: FaceImagePayload) -> np.ndarray:

        buffer = np.frombuffer(payload["bytes"], dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)

        if image is None:
            raise AppException.bad_request(
                f"Cannot decode uploaded image {payload['filename']}"
            )

        return image
