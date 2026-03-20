from enum import Enum


class RedisKey(str, Enum):
    UserSession = "user_session"
    UserSessionByUser = "user_session:{user_id}"


class NotificationChannel(str, Enum):
    WEB = "web"
    MOBILE = "mobile"


NOTIFICATION_EVENT_SUBJECT = "notification.event"


class AuditEventType(str, Enum):
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    UPLOAD_REQUEST_CREATED = "upload_request.created"
    UPLOAD_REQUEST_APPROVED = "upload_request.approved"
    UPLOAD_REQUEST_REJECTED = "upload_request.rejected"


AUDIT_EVENT_SUBJECT = "audit.event"

IMAGE_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif"
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MIN_ENROLL_IMAGES = 3
MAX_ENROLL_IMAGES = 5
