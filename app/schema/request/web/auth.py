from pydantic import BaseModel, EmailStr


class WebAuthRequest(BaseModel):
    email: EmailStr
    password: str

