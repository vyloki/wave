"""
Wave - Listening History Routes
Track what the user listens to with MongoDB storage and optional authentication.
"""

from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.utils.security import get_optional_user
from app.models.playlist import HistoryEntry
from bson import ObjectId
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["History"])


@router.post("", summary="Record a play event")
async def record_play(
    data: HistoryEntry,
    user: dict = Depends(get_optional_user),
    db=Depends(get_db),
):
    """Record that a track was played. Works for both authenticated users and guests."""
    if user and db is not None:
        try:
            doc = {
                "user_id": ObjectId(user["_id"]),
                "video_id": data.video_id,
                "title": data.title,
                "artist": data.artist,
                "thumbnail": data.thumbnail,
                "movie": data.movie or "",
                "language": data.language or "",
                "subtitle": data.subtitle or "",
                "played_at": datetime.now(timezone.utc),
            }
            await db.listening_history.insert_one(doc)
        except Exception as e:
            logger.debug(f"History insert error: {e}")

    return {"message": "Play recorded"}


@router.get("", summary="Get recent listening history")
async def get_history(
    limit: int = Query(default=30, ge=1, le=100),
    user: dict = Depends(get_optional_user),
    db=Depends(get_db),
):
    """Get the user's recent listening history."""
    if not user or db is None:
        return {"history": []}

    try:
        cursor = db.listening_history.find(
            {"user_id": ObjectId(user["_id"])},
        ).sort("played_at", -1).limit(limit)

        history = []
        seen = set()
        async for doc in cursor:
            vid = doc["video_id"]
            if vid not in seen:
                seen.add(vid)
                history.append({
                    "video_id": vid,
                    "title": doc.get("title", ""),
                    "artist": doc.get("artist", ""),
                    "thumbnail": doc.get("thumbnail", ""),
                    "movie": doc.get("movie", ""),
                    "language": doc.get("language", ""),
                    "subtitle": doc.get("subtitle", ""),
                    "played_at": doc.get("played_at"),
                })

        return {"history": history}
    except Exception as e:
        logger.warning(f"History fetch error: {e}")
        return {"history": []}


@router.get("/top", summary="Get most played tracks")
async def get_top(
    limit: int = Query(default=20, ge=1, le=50),
    user: dict = Depends(get_optional_user),
    db=Depends(get_db),
):
    """Get the user's most frequently played tracks."""
    if not user or db is None:
        return {"tracks": []}

    try:
        pipeline = [
            {"$match": {"user_id": ObjectId(user["_id"])}},
            {
                "$group": {
                    "_id": "$video_id",
                    "title": {"$first": "$title"},
                    "artist": {"$first": "$artist"},
                    "thumbnail": {"$first": "$thumbnail"},
                    "play_count": {"$sum": 1},
                    "last_played": {"$max": "$played_at"},
                }
            },
            {"$sort": {"play_count": -1}},
            {"$limit": limit},
        ]
        cursor = db.listening_history.aggregate(pipeline)
        tracks = []
        async for doc in cursor:
            tracks.append({
                "video_id": doc["_id"],
                "title": doc.get("title", ""),
                "artist": doc.get("artist", ""),
                "thumbnail": doc.get("thumbnail", ""),
                "movie": doc.get("movie", ""),
                "language": doc.get("language", ""),
                "subtitle": doc.get("subtitle", ""),
                "play_count": doc.get("play_count", 0),
                "last_played": doc.get("last_played"),
            })
        return {"tracks": tracks}
    except Exception as e:
        logger.warning(f"Top tracks error: {e}")
        return {"tracks": []}


@router.delete("", summary="Clear listening history")
async def clear_history(
    user: dict = Depends(get_optional_user),
    db=Depends(get_db),
):
    """Clear the user's entire listening history."""
    if user and db is not None:
        try:
            await db.listening_history.delete_many(
                {"user_id": ObjectId(user["_id"])}
            )
        except Exception:
            pass
    return {"message": "History cleared"}
