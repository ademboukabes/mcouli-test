from __future__ import annotations

import asyncio
from typing import  List, Literal, Optional, Sequence, Tuple, TypedDict

import cv2
import numpy as np
from insightface.app import FaceAnalysis  # type: ignore
from app.core.exceptions import AppException

BBox = tuple[int, int, int, int]  # (x1, y1, x2, y2)
class FaceImagePayload(TypedDict):
    filename: str
    content_type: str
    bytes: bytes

class FaceStub:
    bbox: Tuple[float, float, float, float]               # bounding box: x1, y1, x2, y2
    det_score: float                                      # detection confidence score
    keypoints: List[Tuple[float, float]]                 # facial landmarks
    gender: Optional[Literal['F','M']] = None            # optional gender
    age: Optional[int] = None                             # optional age
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

        self.model = FaceAnalysis(name=self.model_name, providers=list(self.providers))
        print("[FaceEmbedding] model loaded!")

    def init_model(self) -> None:
        if self.model is None:
            raise ValueError("Model not loaded")

        if self._initialized:
            return

        self.model.prepare(ctx_id=self.ctx_id, det_size=self.det_size) # type: ignore
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

        image_rgb: np.ndarray = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        faces:list[FaceStub] = self.model.get(image_rgb) # type: ignore
        if not faces:
            raise ValueError("No faces detected by the model")

        x1, y1, x2, y2 = bboxes[0]
        target_cx: float = (x1 + x2) / 2
        target_cy: float = (y1 + y2) / 2
        
        best_face: Optional[FaceStub] = None
        best_dist: float = float('inf')

        x1, y1, x2, y2 = bboxes[0]
        target_cx: float = (x1 + x2) / 2
        target_cy: float = (y1 + y2) / 2

        for face in faces:
            fx1, fy1, fx2, fy2 = face.bbox
            cx: float = (fx1 + fx2) / 2
            cy: float = (fy1 + fy2) / 2
            dist: float = np.sqrt((cx - target_cx) ** 2 + (cy - target_cy) ** 2)

            if dist < best_dist:
                best_dist = dist
                best_face = face

        if best_face is None or best_face.embedding is None:
            raise ValueError("Failed to generate embedding for first face")

        embedding: np.ndarray = best_face.embedding.flatten()
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
            raise AppException.bad_request("At least one image is required for enrollment")

        embeddings: list[np.ndarray] = []

        for payload in payloads:
            image = self._decode_image(payload)

            if self.face_embedding.model is None or not self.face_embedding._initialized: # type: ignore
                raise RuntimeError("Face embedding model not ready. Call `prepare()` first.")

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            faces = self.face_embedding.model.get(image_rgb) 
            if not faces:
                raise AppException.bad_request(
                    f"No faces detected in the uploaded image {payload['filename']}"
                )

            # Convert Face objects to list of BBoxes
            bboxes: list[BBox] = []
            for face in faces:
                x1, y1, x2, y2 = face.bbox.astype(int)
                bboxes.append((x1, y1, x2, y2))

            # Step 3: Compute embedding using the AI team's logic
            try:
                embedding = await asyncio.to_thread(
                    self.face_embedding.embed,
                    image,
                    bboxes,  # pass precomputed bboxes
                )
            except (ValueError, RuntimeError) as exc:
                raise AppException.bad_request(
                    f"Face embedding failed for {payload['filename']}: {exc}"
                ) from exc

            embeddings.append(np.array(embedding, dtype=np.float32))

        # Step 4: Average embeddings if multiple images
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
