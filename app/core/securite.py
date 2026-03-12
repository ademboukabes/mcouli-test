from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from passlib.context import CryptContext
import pyotp
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logger import logger


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
