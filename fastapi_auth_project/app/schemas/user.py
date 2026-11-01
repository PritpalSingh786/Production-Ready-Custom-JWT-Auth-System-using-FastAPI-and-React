import re
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator

class RegisterRequest(BaseModel):
    user_id: str = Field(..., min_length=4, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("userId can contain only letters, numbers and underscore")
        return v

class RegisterResponseData(BaseModel):
    user_id: str
    email: EmailStr

class RegisterResponse(BaseModel):
    success: bool
    message: str
    data: RegisterResponseData

class LoginRequest(BaseModel):
    userId: str
    password: str
    platform: str = "web"

class LoginUserData(BaseModel):
    id: UUID
    userId: str
    email: EmailStr

class LoginResponse(BaseModel):
    access: str
    user: LoginUserData
    refresh: Optional[str] = None 

class RefreshRequest(BaseModel):
    refresh: Optional[str] = None
    platform: str = "web"

class RefreshResponse(BaseModel):
    access: str
    refresh: Optional[str] = None

class LogoutRequest(BaseModel):
    refresh: Optional[str] = None
    platform: str = "web"

class LogoutResponse(BaseModel):
    message: str

class ForgotPasswordRequest(BaseModel):
    userId: str

class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str

class PasswordChangeRequest(BaseModel):
    user_id: str
    token: str
    new_password: str = Field(..., min_length=6)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v

class SecurePasswordChangeRequest(BaseModel):
    user_id: str
    token: str
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("New passwords do not match")
        return v

class PasswordChangeResponse(BaseModel):
    success: bool
    message: str
    redirect: Optional[str] = None

class AuthenticatedUser(BaseModel):
    id: UUID
    userId: str
    email: EmailStr

class AuthenticatedResponse(BaseModel):
    msg: str
    user: AuthenticatedUser
    device_id: Optional[str] = None
    platform: Optional[str] = None