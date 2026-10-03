import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def validate_password(value: str) -> str:
    if len(value) < 8 or not re.search(r"[A-Z]", value) or not re.search(r"[a-z]", value) or not re.search(r"\d", value) or not re.search(r"[^A-Za-z0-9]", value):
        raise ValueError("Password must be at least 8 characters and include uppercase, lowercase, digit, and special character")
    return value


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="User", min_length=1, max_length=100)
    email: EmailStr = Field(default="user@gmail.com")
    password: str = Field(default="Newpass@123", min_length=8, max_length=128)
    _validate_password = field_validator("password")(validate_password)


class UserCreateRequest(BaseModel):
    name: str = Field(default="User", min_length=1, max_length=100)
    email: EmailStr = Field(default="user@gmail.com")
    password: str = Field(default="Newpass@123", min_length=8, max_length=128)
    role: str
    _validate_password = field_validator("password")(validate_password)


class LoginRequest(BaseModel):
    email: EmailStr = Field(default="user@gmail.com")
    password: str = Field(default="Newpass@123", min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)

    _validate_password = field_validator("new_password")(validate_password)


class AuthUserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    role_id: int
    is_active: bool
    created_at: str
    updated_at: str


class LoginResponse(TokenResponse):
    user: AuthUserResponse