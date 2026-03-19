from __future__ import annotations

import asyncio
from typing import List, Literal, Optional, Sequence, Tuple, TypedDict

import cv2
import numpy as np
from insightface.app import FaceAnalysis  # type: ignore
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


class FaceEmbedding:
    def __init__(
        self,
        model_name: str = "buffalo_l",
        providers: Sequence[str] = ("CPUExecutionProvider",),
        ctx_id: int = -1,
        det_size: Tuple[int, int] = (640, 640),
    ) -> None:
        self.model: FaceAnalysis | None = None
        self.model_name = model_name
        self.providers = providers
        self.ctx_id = ctx_id
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

        x1, y1, x2, y2 = bboxes[0]
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

        if not payloads:
            raise AppException.bad_request(
                "At least one image is required for enrollment"
            )

        embeddings: list[np.ndarray] = []



        stacked = np.stack(embeddings, axis=0)
        averaged = np.mean(stacked, axis=0)

        return averaged.astype(float).tolist()

    def _decode_image(self, payload: FaceImagePayload) -> np.ndarray:

        buffer = np.frombuffer(payload["bytes"], dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)

        if image is None:
            raise AppException.bad_request(
                f"Cannot decode uploaded image {payload['filename']}"
            )

        return image
