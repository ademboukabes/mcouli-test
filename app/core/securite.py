import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Literal
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict
import pyotp
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logger import logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # Use SHA-256 pre-hashing to overcome bcrypt's 72-byte limit
    pre_hashed = base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())
    logger.debug("hashing password (pre-hashed %s bytes)", len(pre_hashed))
    return pwd_context.hash(pre_hashed)


def verify_password(password: str, hashed: str) -> bool:
    # Verify using the SHA-256 pre-hashed format
    pre_hashed = base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())
    result = pwd_context.verify(pre_hashed, hashed)
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
            (
                datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time())
            ).timestamp()
        ),
    }
    return jwt.encode(
        payload, key=settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def decode_access_mobile_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, key=settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AppException.unauthorized("Token has expired")
    except jwt.InvalidTokenError:
        raise AppException.unauthorized("Invalid token")


def create_raw_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.totp_issuer)


def verify_totp_token_with_window(
    secret: str, token: str, valid_window: int = 8
) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=valid_window)


def generate_Acces_token_stuff(user_id: str, role: str) -> str:
    payload: dict[str, Any] = {
        "user_id": user_id,
        "role": role,
        "exp": int(
            (
                datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time())
            ).timestamp()
        ),
    }
    return jwt.encode(
        payload, key=settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def _get_refresh_cache_aesgcm() -> AESGCM:
    key = base64.b64decode(settings.encryption_key)
    return AESGCM(key)


def encrypt_refresh_cache_payload(plaintext: str) -> str:
    """Encrypt a JSON string for storage in Redis. Returns a base64 string
    safe to store directly (nonce + ciphertext packed together)."""
    aes = _get_refresh_cache_aesgcm()
    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_refresh_cache_payload(encoded: str) -> str:
    """Reverse of encrypt_refresh_cache_payload. Raises on tampering or
    wrong key — treat any exception as 'cache miss'."""
    aes = _get_refresh_cache_aesgcm()
    raw = base64.b64decode(encoded)
    nonce, ciphertext = raw[:12], raw[12:]
    plaintext = aes.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


# class EmbeddingCrypto:
#     _key: bytes = base64.b64decode(settings.FACE_ENCRYPTION_KEY)
#     _aes: AESGCM = AESGCM(_key)

#     @staticmethod
#     def encrypt(embedding: list[float]) -> bytes:
#         data = np.array(embedding, dtype=np.float32).tobytes()

#         nonce = os.urandom(12)
#         ciphertext = EmbeddingCrypto._aes.encrypt(nonce, data, None)

#         return nonce + ciphertext

#     @staticmethod
#     def decrypt(payload: bytes) -> np.ndarray:
#         nonce = payload[:12]
#         ciphertext = payload[12:]

#         data = EmbeddingCrypto._aes.decrypt(nonce, ciphertext, None)

#         return np.frombuffer(data, dtype=np.float32)


class StaffJWTPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    role: str
    type: Literal["access", "refresh"]
    exp: int


def create_access_staff_token(staff_id: str, role: str) -> str:
    """
    Pure stateless access token generation.
    """
    payload = StaffJWTPayload(
        sub=staff_id,
        role=role,
        type="access",
        exp=int(
            (
                datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time())
            ).timestamp()
        ),
    )
    return jwt.encode(
        payload.model_dump(), key=settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def create_refresh_staff_token(staff_id: str, role: str) -> str:
    """
    Stateless refresh token generation (longer expiry).
    """
    payload = StaffJWTPayload(
        sub=staff_id,
        role=role,
        type="refresh",
        exp=int(
            (
                datetime.now(timezone.utc) + timedelta(seconds=Get_expiry_time() * 4)
            ).timestamp()
        ),
    )
    return jwt.encode(
        payload.model_dump(), key=settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def decode_staff_token(token: str) -> StaffJWTPayload:
    """
    Decodes the JWT token and returns a typed Pydantic payload.
    """
    try:
        decoded = jwt.decode(
            token, key=settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return StaffJWTPayload(**decoded)
    except jwt.ExpiredSignatureError:
        raise AppException.unauthorized("Staff token has expired")
    except jwt.InvalidTokenError:
        raise AppException.unauthorized("Invalid staff token")
