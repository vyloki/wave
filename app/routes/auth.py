"""
Wave - Authentication Routes
User registration, login, token refresh, and profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from app.database import get_db
from app.models.user import (
    UserRegister,
    UserLogin,
    UserProfileUpdate,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
    MessageResponse,
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.config import settings
from bson import ObjectId
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def user_to_response(user: dict) -> UserResponse:
    """Convert a MongoDB user document to a UserResponse model."""
    return UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user["email"],
        display_name=user.get("display_name"),
        avatar_url=user.get("avatar_url"),
        created_at=user.get("created_at"),
        liked_tracks=user.get("liked_tracks", []),
        settings=user.get("settings", {
            "theme": "sand",
            "quality": "high",
            "language_preference": []
        }),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
async def register(data: UserRegister, db=Depends(get_db)):
    """
    Register a new user account.

    - Validates email uniqueness
    - Validates username uniqueness
    - Hashes password with bcrypt
    - Returns JWT access + refresh tokens
    """
    # Check if email already exists
    existing_email = await db.users.find_one({"email": data.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Check if username already exists
    existing_username = await db.users.find_one({"username": data.username})
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )

    # Create user document
    now = datetime.now(timezone.utc)
    user_doc = {
        "username": data.username,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "display_name": data.display_name or data.username,
        "avatar_url": None,
        "created_at": now,
        "updated_at": now,
        "liked_tracks": [],
        "settings": {
            "theme": "sand",
            "quality": "high",
            "language_preference": []
        }
    }

    # Insert into MongoDB
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    logger.info(f"✅ New user registered: {data.username} ({data.email})")

    # Generate tokens
    user_id = str(result.inserted_id)
    access_token = create_access_token(user_id, data.username)
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=user_to_response(user_doc),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password"
)
async def login(data: UserLogin, db=Depends(get_db)):
    """
    Authenticate a user with email and password.
    Returns JWT access + refresh tokens on success.
    """
    # Find user by email
    user = await db.users.find_one({"email": data.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    logger.info(f"✅ User logged in: {user['username']}")

    # Generate tokens
    user_id = str(user["_id"])
    access_token = create_access_token(user_id, user["username"])
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=user_to_response(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an expired access token"
)
async def refresh_token(data: RefreshTokenRequest, db=Depends(get_db)):
    """
    Use a valid refresh token to get a new access token.
    """
    # Decode the refresh token
    payload = decode_token(data.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type — expected refresh token"
        )

    user_id = payload.get("sub")
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Generate new tokens
    new_access_token = create_access_token(
        str(user["_id"]),
        user["username"]
    )
    new_refresh_token = create_refresh_token(str(user["_id"]))

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=user_to_response(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile"
)
async def get_me(user: dict = Depends(get_current_user)):
    """
    Get the profile of the currently authenticated user.
    Requires a valid JWT access token.
    """
    return user_to_response(user)


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="Update user profile"
)
async def update_profile(
    data: UserProfileUpdate,
    user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Update the current user's profile information.
    Only provided fields will be updated.
    """
    update_fields = {}

    if data.display_name is not None:
        update_fields["display_name"] = data.display_name
    if data.avatar_url is not None:
        update_fields["avatar_url"] = data.avatar_url
    if data.settings is not None:
        # Merge settings (don't replace entirely)
        current_settings = user.get("settings", {})
        current_settings.update(data.settings)
        update_fields["settings"] = current_settings

    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {"$set": update_fields}
        )

    # Fetch updated user
    updated_user = await db.users.find_one(
        {"_id": ObjectId(user["_id"])}
    )
    updated_user["_id"] = str(updated_user["_id"])

    return user_to_response(updated_user)


@router.post(
    "/like/{video_id}",
    response_model=MessageResponse,
    summary="Toggle like on a track"
)
async def toggle_like(
    video_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Toggle like/unlike on a track."""
    liked_tracks = user.get("liked_tracks", [])

    if video_id in liked_tracks:
        # Unlike
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {"$pull": {"liked_tracks": video_id}}
        )
        return MessageResponse(message="Track unliked")
    else:
        # Like
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {"$addToSet": {"liked_tracks": video_id}}
        )
        return MessageResponse(message="Track liked")
