"""
Wave - Authentication Routes
User registration, login, token refresh, and profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import Optional, Dict, Any
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
    summary="Toggle like on a track"
)
async def toggle_like(
    video_id: str,
    body: Optional[Dict[str, Any]] = Body(default=None),
    user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Toggle like/unlike on a track with full track metadata preservation."""
    liked_tracks = user.get("liked_tracks", [])
    user_id_str = str(user["_id"])
    track_data = body.get("track") if (body and isinstance(body, dict)) else None

    if video_id in liked_tracks:
        # Unlike
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {"$pull": {"liked_tracks": video_id}}
        )
        if db is not None:
            await db.liked_songs.delete_one({"user_id": user_id_str, "video_id": video_id})
        return {"status": "unliked", "is_liked": False, "message": "Track unliked"}
    else:
        # Like
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {"$addToSet": {"liked_tracks": video_id}}
        )
        if db is not None:
            # If track_data was not sent, check song_cache or stream_cache
            if not track_data:
                cached = await db.song_cache.find_one({"_id": video_id})
                if cached:
                    track_data = cached
                else:
                    stream_cached = await db.stream_cache.find_one({"_id": video_id})
                    if stream_cached:
                        track_data = stream_cached

            title = (track_data.get("title") or track_data.get("track_name") or "Liked Song") if track_data else "Liked Song"
            artist = (track_data.get("artist") or "") if track_data else ""
            movie = (track_data.get("movie") or "") if track_data else ""
            language = (track_data.get("language") or "") if track_data else ""
            thumbnail = (track_data.get("thumbnail") or track_data.get("album_art") or "") if track_data else ""
            duration = int((track_data.get("duration") or 0)) if track_data else 0
            is_extracted = bool(track_data.get("is_extracted") or video_id.startswith("ext_")) if track_data else video_id.startswith("ext_")
            platform = (track_data.get("platform") or "YouTube") if track_data else "YouTube"

            song_doc = {
                "user_id": user_id_str,
                "video_id": video_id,
                "title": title,
                "track_name": title,
                "artist": artist,
                "movie": movie,
                "language": language,
                "thumbnail": thumbnail,
                "album_art": thumbnail,
                "duration": duration,
                "is_extracted": is_extracted,
                "platform": platform,
                "track": track_data or {
                    "video_id": video_id,
                    "title": title,
                    "artist": artist,
                    "movie": movie,
                    "language": language,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "is_extracted": is_extracted,
                    "platform": platform
                },
                "liked_at": datetime.now(timezone.utc),
            }

            await db.liked_songs.update_one(
                {"user_id": user_id_str, "video_id": video_id},
                {"$set": song_doc},
                upsert=True
            )

        return {"status": "liked", "is_liked": True, "message": "Track liked"}


@router.get(
    "/liked",
    summary="Get all liked tracks"
)
async def get_liked_tracks(
    user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Retrieve full track objects for all liked songs of the user."""
    user_id_str = str(user["_id"])
    if db is None:
        return {"tracks": [], "total": 0}

    # 1. Lookup from liked_songs collection (instant, preserved metadata)
    cursor = db.liked_songs.find({"user_id": user_id_str}).sort("liked_at", -1)
    docs = await cursor.to_list(200)

    tracks = []
    seen_ids = set()

    for doc in docs:
        vid = doc.get("video_id")
        if vid and vid not in seen_ids:
            seen_ids.add(vid)
            t = doc.get("track") or doc
            t["video_id"] = vid
            t["title"] = doc.get("title") or t.get("title") or "Liked Song"
            t["track_name"] = t["title"]
            t["artist"] = doc.get("artist") or t.get("artist") or ""
            t["movie"] = doc.get("movie") or t.get("movie") or ""
            t["language"] = doc.get("language") or t.get("language") or ""
            t["thumbnail"] = doc.get("thumbnail") or t.get("thumbnail") or ""
            t["album_art"] = t["thumbnail"]
            t["duration"] = doc.get("duration") or t.get("duration") or 0
            t["is_extracted"] = doc.get("is_extracted") or vid.startswith("ext_")
            t["is_liked"] = True
            tracks.append(t)

    # 2. Backfill any IDs in user.liked_tracks not yet in liked_songs
    user_liked_ids = user.get("liked_tracks", [])
    for vid in user_liked_ids:
        if vid not in seen_ids:
            cached = await db.song_cache.find_one({"_id": vid})
            if cached:
                cached.pop("_id", None)
                cached["video_id"] = vid
                cached["is_liked"] = True
                tracks.append(cached)
                seen_ids.add(vid)
            else:
                stream_cached = await db.stream_cache.find_one({"_id": vid})
                if stream_cached:
                    tracks.append({
                        "video_id": vid,
                        "title": stream_cached.get("title") or "Liked Track",
                        "artist": stream_cached.get("artist") or "",
                        "thumbnail": "",
                        "duration": stream_cached.get("duration", 0),
                        "is_extracted": vid.startswith("ext_"),
                        "is_liked": True
                    })
                else:
                    tracks.append({
                        "video_id": vid,
                        "title": "Liked Song",
                        "artist": "",
                        "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if not vid.startswith("ext_") else "",
                        "duration": 0,
                        "is_liked": True,
                    })
                seen_ids.add(vid)

    return {"tracks": tracks, "total": len(tracks)}
