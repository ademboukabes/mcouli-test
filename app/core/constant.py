from enum import Enum


class RedisKey(str, Enum):
    UserSession = "user_session"
    INVALID_TOKEN_SET_KEY = "notifications:invalid_tokens"
    MobileSessionCache = "session:{session_id}"


NOTIFICATION_EVENT_SUBJECT = "notification_event"
AUDIT_EVENT_SUBJECT = "audit.event"
FINAL_BUCKET_CLEANUP_SUBJECT = "ai.final_bucket.completed"
FINAL_BUCKET_CLEANUP_STREAM = "ai-final-bucket-cleanup"
FINAL_BUCKET_CLEANUP_DURABLE_NAME = "ai-final-bucket-cleaner"
UPLOAD_GROUP_IMPORT_SUBJECT = "staff.upload_group.import.requested"
UPLOAD_GROUP_IMPORT_STREAM = "staff-upload-group-import"
UPLOAD_GROUP_IMPORT_DURABLE_NAME = "staff-upload-group-import-worker"


class AuditEventType(str, Enum):
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    FACE_ENROLLMENT_ATTEMPT = "face_enrollment.attempt"
    UPLOAD_REQUEST_CREATED = "upload_request.created"
    UPLOAD_REQUEST_APPROVED = "upload_request.approved"
    UPLOAD_REQUEST_REJECTED = "upload_request.rejected"
    PHOTO_PROCESSED = "photo.processed"
    PHOTO_APPROVAL_DECIDED = "photo_approval.decided"


IMAGE_ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif"
}

DEFAULT_CONTENT_TYPE = "application/octet-stream"
DRIVE_ALLOWED_HOSTS = {"drive.google.com", "docs.google.com"}
MINIO_URL_PREFIX = "minio://"

IMAGES_BUCKET_NAME = "images"
DOCUMENTS_BUCKET_NAME = "documents"
WA_SIM_BUCKET_NAME = "wa-sim"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files/{file_id}"

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MIN_IMAGE_DIM = 64
MAX_IMAGE_DIM = 4096
MIN_ENROLL_IMAGES = 3
MAX_ENROLL_IMAGES = 5

ENROLL_RATE_LIMIT_MAX = 5
ENROLL_RATE_LIMIT_WINDOW = 3600
ENROLL_IN_PROGRESS_TTL_SECONDS = 300
