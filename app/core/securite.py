import base64
from datetime import datetime, timedelta, timezone
import os
from typing import Any
import jwt
import numpy as np
from passlib.context import CryptContext
import pyotp
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logger import logger
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_BCRYPT_MAX_LEN = 72


def _normalize_password(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_LEN]


def hash_password(password: str) -> str:
    normalized = _normalize_password(password)
    logger.debug("hashing password (normalized %s bytes)", len(normalized))
    return pwd_context.hash(normalized)


def verify_password(password: str, hashed: str) -> bool:
    normalized = _normalize_password(password)
    result = pwd_context.verify(normalized, hashed)
    logger.debug("password verification result: %s", result)
    return result


def Get_expiry_time() -> int:
    if settings.environment == "dev":
        expiry = 60 * 60 * 24 * 7
    else:
        expiry = 60 * 60 * 24
    return expiry


def create_acces_mobile_token(session_id: str) -> str:
    payload: dict[str, Any] = {
        "session_id": session_id,
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time())).timestamp()
        ),
    }
    return jwt.encode(payload, key=settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_mobile_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, key=settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise AppException.unauthorized("Token has expired")
    except jwt.InvalidTokenError:
        raise AppException.unauthorized("Invalid token")


def create_refresh_mobile_token(session_id: str) -> str:
    payload: dict[str, Any] = {
        "session_id": session_id,
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time() * 4)).timestamp()
        ),
    }
    return jwt.encode(payload, key=settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_refresh_mobile_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, key=settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise AppException.unauthorized("Token has expired")
    except jwt.InvalidTokenError:
        raise AppException.unauthorized("Invalid token")


def create_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.totp_issuer)


def verify_totp_token_with_window(secret: str, token: str, valid_window: int = 8) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=valid_window)


def generate_Acces_token_stuff(user_id: str, role: str) -> str:
    payload: dict[str, Any] = {
        "user_id": user_id,
        "role": role,
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time())).timestamp()
        ),
    }
    return jwt.encode(payload, key=settings.jwt_secret, algorithm=settings.jwt_algorithm)

<<<<<<< HEAD



class EmbeddingCrypto:
    _key: bytes = base64.b64decode(settings.FACE_ENCRYPTION_KEY)
    _aes: AESGCM = AESGCM(_key)

    @staticmethod
    def encrypt(embedding: list[float]) -> bytes:
        data = np.array(embedding, dtype=np.float32).tobytes()

        nonce = os.urandom(12)
        ciphertext = EmbeddingCrypto._aes.encrypt(nonce, data, None)

        return nonce + ciphertext

    @staticmethod
    def decrypt(payload: bytes) -> np.ndarray:
        nonce = payload[:12]
        ciphertext = payload[12:]

        data = EmbeddingCrypto._aes.decrypt(nonce, ciphertext, None)

        return np.frombuffer(data, dtype=np.float32)
=======
def create_access_staff_token(session_id: str, staff_id: str, role: str) -> str:
    """
    Generates a staff access token containing the session_id, 
    allowing for server-side session invalidation.
    """
    payload: dict[str, Any] = {
        "sid": session_id,
        "sub": staff_id,
        "role": role,
        "type": "access",
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time())).timestamp()
        ),
    }
    return jwt.encode(payload, key=settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_staff_token(session_id: str, staff_id: str) -> str:
    """
    Generates a longer-lived refresh token for staff web sessions.
    """
    payload: dict[str, Any] = {
        "sid": session_id,
        "sub": staff_id,
        "type": "refresh",
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time() * 4)).timestamp()
        ),
    }
    return jwt.encode(payload, key=settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_staff_token(token: str) -> dict[str, Any]:
    """
    Universal decoder for staff tokens.
    """
    try:
        payload = jwt.decode(token, key=settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise AppException.unauthorized("Staff token has expired")
    except jwt.InvalidTokenError:
        raise AppException.unauthorized("Invalid staff token")
>>>>>>> 115b953 (event (create edit archive, + join) after testing)
