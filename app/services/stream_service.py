"""
Wave - Stream Service
Audio stream URL management with caching and expiry handling.
"""

from app.services.youtube_service import get_stream_url
from app.database import database
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# Stream URLs expire after approximately 6 hours on YouTube
STREAM_URL_TTL = timedelta(hours=5)  # Use 5h to be safe


async def get_cached_stream_url(video_id: str) -> str | None:
    """
    Get a stream URL, using cache if available and not expired.
    Falls back to extracting a fresh URL from YouTube.

    Returns the direct audio stream URL or None on failure.
    """
    db = database.db
    if db is None:
        # Database not connected, extract directly
        result = await get_stream_url(video_id)
        return result["url"] if result else None

    # Check cache for a non-expired stream URL
    cached = await db.stream_cache.find_one({
        "_id": video_id,
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })

    if cached and cached.get("stream_url"):
        logger.info(f"📦 Stream cache hit: {video_id}")
        return cached["stream_url"]

    # Extract fresh URL from YouTube
    result = await get_stream_url(video_id)
    if not result or not result.get("url"):
        logger.error(f"❌ Failed to get stream URL for {video_id}")
        return None

    # Cache the stream URL with expiry
    await db.stream_cache.update_one(
        {"_id": video_id},
        {
            "$set": {
                "stream_url": result["url"],
                "format": result.get("format", ""),
                "ext": result.get("ext", ""),
                "duration": result.get("duration", 0),
                "cached_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + STREAM_URL_TTL,
            }
        },
        upsert=True,
    )

    logger.info(f"🎵 Fresh stream URL cached: {video_id}")
    return result["url"]
