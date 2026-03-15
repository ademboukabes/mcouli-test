from enum import Enum


class RedisKey(str, Enum):
    UserSession = "user_session"
    UserSessionByUser = "user_session:{user_id}"

IMAGE_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif"
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MIN_ENROLL_IMAGES = 3
MAX_ENROLL_IMAGES = 5