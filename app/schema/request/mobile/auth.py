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
    physical_device_id: UUID

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
    @field_validator("password")
    @classmethod
    def _validate_password_complexity(cls, value: str) -> str:
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one digit")
        if not any(not c.isalnum() for c in value):
            raise ValueError("Password must contain at least one special character")
        return value


class MobileLoginRequest(MobileAuthBaseRequest):
    pass


class RegisterVerifyRequest(MobileAuthBaseRequest):
    otp: str = Field(..., min_length=6, max_length=6, description="The 6-digit OTP code sent via email")





class ResendOtpRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().lower()


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UpdateDeviceTokenRequest(BaseModel):
    device_id: UUID
    push_token: str


class InactivateDeviceRequest(BaseModel):
    device_id: UUID
