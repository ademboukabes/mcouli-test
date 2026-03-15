import cv2
import numpy as np
from insightface.app import FaceAnalysis

class FaceEmbedding:
    def __init__(self):
        self.model = None

    def load_model(self):
        self.model = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        print("[FaceEmbedding] model loaded!")

    def init_model(self):
        if self.model is None:
            raise ValueError("Model not loaded")
        self.model.prepare(ctx_id=-1, det_size=(640, 640))
        print("[FaceEmbedding] model initialized")

    def embed(self, image, bboxes):
        if len(bboxes) == 0:
            raise ValueError("No faces to embed")

        # Convert BGR to RGB for insightface
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Run full face analysis — detects faces and computes embeddings internally
        faces = self.model.get(image_rgb)

        if len(faces) == 0:
            raise ValueError("No faces detected by the model")

        # Match to the first bbox by picking the closest detected face
        x1, y1, x2, y2 = bboxes[0]
        target_cx = (x1 + x2) / 2
        target_cy = (y1 + y2) / 2

        best_face = None
        best_dist = float('inf')

        for face in faces:
            fx1, fy1, fx2, fy2 = face.bbox
            cx = (fx1 + fx2) / 2
            cy = (fy1 + fy2) / 2
            dist = np.sqrt((cx - target_cx) ** 2 + (cy - target_cy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_face = face

        if best_face is None or best_face.embedding is None:
            raise ValueError("Failed to generate embedding for first face")

        return best_face.embedding.flatten().tolist()

    