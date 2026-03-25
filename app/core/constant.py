from enum import Enum


class RedisKey(str, Enum):
    UserSession = "user_session"
    UserSessionByUser = "user_session:{user_id}"
    INVALID_TOKEN_SET_KEY=  "notifications:invalid_tokens"


NOTIFICATION_EVENT_SUBJECT = "notification_event"
AUDIT_EVENT_SUBJECT = "audit.event"
FINAL_BUCKET_CLEANUP_SUBJECT = "ai.final_bucket.completed"
FINAL_BUCKET_CLEANUP_STREAM = "ai-final-bucket-cleanup"
FINAL_BUCKET_CLEANUP_DURABLE_NAME = "ai-final-bucket-cleaner"


class AuditEventType(str, Enum):
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    UPLOAD_REQUEST_CREATED = "upload_request.created"
    UPLOAD_REQUEST_APPROVED = "upload_request.approved"
    UPLOAD_REQUEST_REJECTED = "upload_request.rejected"


    BlacklistedSession = "blacklist:session:{session_id}"

IMAGE_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif"
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MIN_ENROLL_IMAGES = 3
MAX_ENROLL_IMAGES = 5
