from enum import Enum


class RedisKey(str, Enum):
    UserSession = "user_session"
    UserSessionByUser = "user_session:{user_id}"

<<<<<<< HEAD
IMAGE_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif"
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MIN_ENROLL_IMAGES = 3
MAX_ENROLL_IMAGES = 5
=======
    StaffSession = "staff_session"
    StaffSessionByStaff = "staff_session:{staff_id}"
>>>>>>> 115b953 (event (create edit archive, + join) after testing)
