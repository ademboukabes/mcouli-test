from pydantic import BaseModel, EmailStr, Field, ValidationInfo, field_validator
from uuid import UUID
from app.core.config import settings


class MobileAuthBaseRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(
        ...,
        min_length=settings.MOBILE_AUTH_PASSWORD_MIN_LEN,
        max_length=settings.MOBILE_AUTH_PASSWORD_MAX_LEN,
    )
    device_name: str = Field(
        ...,
        min_length=1,
        max_length=settings.MOBILE_AUTH_DEVICE_NAME_MAX_LEN,
    )
    device_type: str = Field(
        ...,
        min_length=1,
        max_length=settings.MOBILE_AUTH_DEVICE_TYPE_MAX_LEN,
    )
    device_id: UUID

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator("password", "device_name", "device_type", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{info.field_name} must not be empty")
        if info.field_name == "password":
            return stripped
        if info.field_name == "device_type":
            return stripped.lower()
        return stripped


class MobileRegisterRequest(MobileAuthBaseRequest):
    pass


class MobileLoginRequest(MobileAuthBaseRequest):
    pass





class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UpdateDeviceTokenRequest(BaseModel):
    device_id: UUID
    push_token: str


class InactivateDeviceRequest(BaseModel):
    device_id: UUID
