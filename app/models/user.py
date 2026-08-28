"""
Wave - User Data Models
Pydantic models for user registration, login, profile, and DB representation.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# --- Request Models (what the client sends) ---

class UserRegister(BaseModel):
    """Schema for user registration request."""
    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Username (alphanumeric + underscores, 3-30 chars)"
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address"
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Password (6-128 chars)"
    )
    display_name: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Display name shown in the app"
    )


class UserLogin(BaseModel):
    """Schema for user login request."""
    email: EmailStr = Field(
        ...,
        description="Email address"
    )
    password: str = Field(
        ...,
        description="Password"
    )


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""
    display_name: Optional[str] = Field(
        default=None,
        max_length=50
    )
    avatar_url: Optional[str] = None
    settings: Optional[dict] = None


# --- Response Models (what the server returns) ---

class UserResponse(BaseModel):
    """Schema for user data returned to the client."""
    id: str = Field(..., description="User ID")
    username: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    liked_tracks: List[str] = []
    settings: dict = Field(default_factory=lambda: {
        "theme": "sand",
        "quality": "high",
        "language_preference": []
    })


class TokenResponse(BaseModel):
    """Schema for JWT token response after login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        ...,
        description="Access token expiry in seconds"
    )
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True
