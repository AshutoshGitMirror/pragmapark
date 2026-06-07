from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LogoutResponse(BaseModel):
    message: str = "logged_out"


class AuthUser(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    organization: str = ""


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(
        min_length=8, max_length=128
    )  # password min 8 chars; hashed output fits in String(255)
    full_name: str = Field(default="", max_length=255)
    organization: str = Field(default="", max_length=255)
    role: str = Field(default="", max_length=50)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
