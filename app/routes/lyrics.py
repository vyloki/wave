"""
Wave - Lyrics Routes
Fetch and serve song lyrics with sync timestamps.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.lyrics_service import get_lyrics
from app.utils.security import get_optional_user
from app.database import get_db
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lyrics", tags=["Lyrics"])


@router.get(
    "/{video_id}",
    summary="Get lyrics for a track"
)
async def fetch_lyrics(
    video_id: str,
    title: str = Query("", description="Track title"),
    artist: str = Query("", description="Artist name"),
    duration: int = Query(0, description="Track duration in seconds"),
    user=Depends(get_optional_user),
    db=Depends(get_db),
):
    """Fetch synced or plain lyrics for a track."""
    # Check cache
    if db is not None:
        try:
            cached = await db.lyrics_cache.find_one({"_id": video_id})
            if cached:
                logger.info(f"📦 Lyrics cache hit: {video_id}")
                return {
                    "video_id": video_id,
                    "synced": cached.get("synced_lyrics", []),
                    "plain": cached.get("plain_lyrics", ""),
                    "has_synced": len(cached.get("synced_lyrics", [])) > 0,
                    "source": cached.get("source", "cache"),
                }
        except Exception:
            pass

    # Get track info from song_cache if not provided
    if not title and db is not None:
        try:
            track_cache = await db.song_cache.find_one({"_id": video_id})
            if track_cache:
                title = track_cache.get("track_name") or track_cache.get("title", "")
                artist = track_cache.get("artist", "")
                duration = track_cache.get("duration", 0)
        except Exception:
            pass

    if not title:
        title = f"track {video_id}"

    # Fetch from LRCLIB
    result = await get_lyrics(
        track_name=title,
        artist_name=artist,
        duration=duration,
    )

    if result:
        if db is not None:
            try:
                await db.lyrics_cache.update_one(
                    {"_id": video_id},
                    {
                        "$set": {
                            **result,
                            "cached_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
            except Exception:
                pass

        return {
            "video_id": video_id,
            "synced": result.get("synced_lyrics", []),
            "plain": result.get("plain_lyrics", ""),
            "has_synced": len(result.get("synced_lyrics", [])) > 0,
            "source": result.get("source", "lrclib"),
        }

    return {
        "video_id": video_id,
        "synced": [],
        "plain": "",
        "has_synced": False,
        "source": "none",
    }
