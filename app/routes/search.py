"""
Wave - Search Routes
Music search endpoints with YouTube + MusicBrainz enrichment and DB caching.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.utils.security import get_optional_user
from app.services.youtube_service import (
    search_youtube,
    get_video_info,
    get_youtube_suggestions,
)
from app.services.metadata_service import search_with_metadata, enrich_track
from app.database import get_db
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("", summary="Search for songs")
async def search(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(default=20, ge=1, le=50, description="Max results"),
    enrich: bool = Query(default=True, description="Enrich metadata"),
    user: dict = Depends(get_optional_user),
    db=Depends(get_db),
):
    """
    Search for songs by query.
    Caches in MongoDB when available, falls back to direct YouTube search.
    """
    cache_key = f"search:{q.lower().strip()}:{limit}"

    # Check cache
    if db is not None:
        try:
            cached = await db.search_cache.find_one({
                "_id": cache_key,
                "cached_at": {"$gt": datetime.now(timezone.utc).replace(hour=0, minute=0)}
            })
            if cached and cached.get("results"):
                return {
                    "query": q,
                    "results": cached["results"],
                    "total": len(cached["results"]),
                    "cached": True,
                }
        except Exception as e:
            logger.debug(f"Search cache lookup skipped: {e}")

    # Perform search
    if enrich:
        results = await search_with_metadata(q, limit)
    else:
        results = await search_youtube(q, limit)

    # Cache results if DB is available
    if db is not None and results:
        try:
            await db.search_cache.update_one(
                {"_id": cache_key},
                {
                    "$set": {
                        "results": results,
                        "cached_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            for track in results:
                if track.get("video_id"):
                    await db.song_cache.update_one(
                        {"_id": track["video_id"]},
                        {
                            "$set": {
                                **track,
                                "cached_at": datetime.now(timezone.utc),
                            }
                        },
                        upsert=True,
                    )
        except Exception as e:
            logger.debug(f"Search cache save skipped: {e}")

    return {
        "query": q,
        "results": results,
        "total": len(results),
        "cached": False,
    }


@router.get("/suggestions", summary="Get autocomplete suggestions")
async def suggestions(
    q: str = Query(..., min_length=1, max_length=100, description="Query"),
):
    """Get clean music-focused autocomplete suggestions."""
    from app.services.youtube_service import get_youtube_suggestions
    results = await get_youtube_suggestions(q)
    return {"query": q, "suggestions": results}


@router.get("/track/{video_id}", summary="Get track details")
async def get_track(
    video_id: str,
    user: dict = Depends(get_optional_user),
    db=Depends(get_db),
):
    """Get detailed information for a track."""
    if db is not None:
        try:
            cached = await db.song_cache.find_one({"_id": video_id})
            if cached:
                if user:
                    cached["is_liked"] = video_id in user.get("liked_tracks", [])
                cached.pop("_id", None)
                cached["video_id"] = video_id
                return cached
        except Exception as e:
            logger.debug(f"Track cache lookup skipped: {e}")

    track = await get_video_info(video_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    track = await enrich_track(track)

    if db is not None:
        try:
            await db.song_cache.update_one(
                {"_id": video_id},
                {
                    "$set": {
                        **track,
                        "cached_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
        except Exception:
            pass

    if user:
        track["is_liked"] = video_id in user.get("liked_tracks", [])

    return track
