from functools import lru_cache

from app.service.face_embedding import FaceEmbedding


@lru_cache(maxsize=1)
def get_face_embedding() -> FaceEmbedding:
    #retuern cached instance of the model in this process
    face_embedding = FaceEmbedding()
    face_embedding.prepare()
    return face_embedding
