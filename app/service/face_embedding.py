from __future__ import annotations

import asyncio
from typing import Any, Sequence, Tuple, TypedDict

import cv2
import numpy as np
from insightface.app import FaceAnalysis  # type: ignore
from app.core.exceptions import AppException

BBox = Tuple[int, int, int, int]
class FaceImagePayload(TypedDict):
    filename: str
    content_type: str
    bytes: bytes


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

        self.model = FaceAnalysis(name=self.model_name, providers=list(self.providers))
        print("[FaceEmbedding] model loaded!")

    def init_model(self) -> None:
        if self.model is None:
            raise ValueError("Model not loaded")

        if self._initialized:
            return

        self.model.prepare(ctx_id=self.ctx_id, det_size=self.det_size)
        self._initialized = True
        print("[FaceEmbedding] model initialized")

    def prepare(self) -> None:
        self.load_model()
        self.init_model()

    def _normalize_bbox(self, bbox: BBox, image_shape: Tuple[int, int]) -> BBox:
        height, width = image_shape
        x1, y1, x2, y2 = (int(round(value)) for value in bbox)

        x1 = max(0, min(width, x1))
        x2 = max(0, min(width, x2))
        y1 = max(0, min(height, y1))
        y2 = max(0, min(height, y2))

        if x2 <= x1 or y2 <= y1:
            raise ValueError("Invalid bounding box")

        return x1, y1, x2, y2

    def _crop_face(self, image_rgb: np.ndarray, bbox: BBox) -> np.ndarray:
        x1, y1, x2, y2 = self._normalize_bbox(bbox, image_rgb.shape[:2])
        return image_rgb[y1:y2, x1:x2]

    def embed(self, image: np.ndarray, bboxes: Sequence[BBox] | None = None) -> list[float]:
        if self.model is None or not self._initialized:
            raise RuntimeError("Face embedding model is not ready")

        if bboxes is not None and not bboxes:
            raise ValueError("No faces to embed")

        # Convert BGR to RGB and crop to the first bounding box that needs an embedding
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        faces: list[Any]

        if bboxes:
            face_region = self._crop_face(image_rgb, bboxes[0])
            faces = self.model.get(face_region)
        else:
            faces = self.model.get(image_rgb)

        if not faces:
            raise ValueError("No faces detected in the provided region")

        first_face = faces[0]
        if first_face.embedding is None:
            raise ValueError("Failed to generate embedding for the requested face")

        return first_face.embedding.flatten().tolist()


class FaceEmbeddingService:
    def __init__(self, face_embedding: FaceEmbedding | None = None) -> None:
        self.face_embedding = face_embedding or FaceEmbedding()
        self.face_embedding.prepare()

    async def compute_average_embedding(
        self,
        payloads: Sequence[FaceImagePayload],
    ) -> list[float]:
        if not payloads:
            raise AppException.bad_request("At least one image is required for enrollment")

        embeddings: list[np.ndarray] = []
        for payload in payloads:
            image = self._decode_image(payload)
            try:
                embedding = await asyncio.to_thread(
                    self.face_embedding.embed,
                    image,
                )
            except (ValueError, RuntimeError) as exc:
                raise AppException.bad_request(
                    f"Face detection failed for {payload['filename']}: {exc}"
                ) from exc

            embeddings.append(np.array(embedding, dtype=np.float32))

        stacked = np.stack(embeddings, axis=0)
        averaged = np.mean(stacked, axis=0)

        return averaged.astype(float).tolist()

    def _decode_image(self, payload: FaceImagePayload) -> np.ndarray:
        buffer = np.frombuffer(payload["bytes"], dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise AppException.bad_request(
                f"Cannot decode the uploaded image {payload['filename']}"
            )

        return image
