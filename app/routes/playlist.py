"""
Wave - Playlist Routes
CRUD operations for user playlists.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from app.database import get_db
from app.utils.security import get_current_user
from app.models.playlist import (
    PlaylistCreate, PlaylistUpdate, PlaylistResponse,
    AddTrackRequest,
)
from bson import ObjectId
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/playlists", tags=["Playlists"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a playlist")
async def create_playlist(
    data: PlaylistCreate,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": ObjectId(user["_id"]),
        "name": data.name,
        "description": data.description or "",
        "tracks": [],
        "cover_url": "",
        "created_at": now,
        "updated_at": now,
    }
    result = await db.playlists.insert_one(doc)
    logger.info(f"✅ Playlist created: {data.name}")
    return {
        "id": str(result.inserted_id),
        "name": data.name,
        "description": data.description or "",
        "track_count": 0,
        "created_at": now,
    }


@router.get("", summary="List user playlists")
async def list_playlists(
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    cursor = db.playlists.find({"user_id": ObjectId(user["_id"])})
    playlists = []
    async for doc in cursor:
        playlists.append({
            "id": str(doc["_id"]),
            "name": doc["name"],
            "description": doc.get("description", ""),
            "track_count": len(doc.get("tracks", [])),
            "cover_url": doc.get("cover_url", ""),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        })
    return {"playlists": playlists}


@router.get("/{playlist_id}", summary="Get playlist details")
async def get_playlist(
    playlist_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    doc = await db.playlists.find_one({
        "_id": ObjectId(playlist_id),
        "user_id": ObjectId(user["_id"]),
    })
    if not doc:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "description": doc.get("description", ""),
        "tracks": doc.get("tracks", []),
        "track_count": len(doc.get("tracks", [])),
        "cover_url": doc.get("cover_url", ""),
        "created_at": doc.get("created_at"),
    }


@router.put("/{playlist_id}", summary="Update playlist")
async def update_playlist(
    playlist_id: str,
    data: PlaylistUpdate,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    update = {"updated_at": datetime.now(timezone.utc)}
    if data.name is not None:
        update["name"] = data.name
    if data.description is not None:
        update["description"] = data.description

    result = await db.playlists.update_one(
        {"_id": ObjectId(playlist_id), "user_id": ObjectId(user["_id"])},
        {"$set": update},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"message": "Playlist updated"}


@router.delete("/{playlist_id}", summary="Delete playlist")
async def delete_playlist(
    playlist_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.playlists.delete_one({
        "_id": ObjectId(playlist_id),
        "user_id": ObjectId(user["_id"]),
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"message": "Playlist deleted"}


@router.post("/{playlist_id}/tracks", summary="Add track to playlist")
async def add_track(
    playlist_id: str,
    data: AddTrackRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    track = {
        "video_id": data.video_id,
        "title": data.title,
        "artist": data.artist,
        "duration": data.duration,
        "thumbnail": data.thumbnail,
        "added_at": datetime.now(timezone.utc),
    }
    result = await db.playlists.update_one(
        {"_id": ObjectId(playlist_id), "user_id": ObjectId(user["_id"])},
        {
            "$push": {"tracks": track},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Update cover with first track thumbnail if no cover set
    playlist = await db.playlists.find_one({"_id": ObjectId(playlist_id)})
    if playlist and not playlist.get("cover_url") and data.thumbnail:
        await db.playlists.update_one(
            {"_id": ObjectId(playlist_id)},
            {"$set": {"cover_url": data.thumbnail}},
        )

    return {"message": "Track added to playlist"}


@router.delete("/{playlist_id}/tracks/{video_id}", summary="Remove track from playlist")
async def remove_track(
    playlist_id: str,
    video_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    result = await db.playlists.update_one(
        {"_id": ObjectId(playlist_id), "user_id": ObjectId(user["_id"])},
        {
            "$pull": {"tracks": {"video_id": video_id}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"message": "Track removed from playlist"}
