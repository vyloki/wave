"""
Wave - Background Tasks (Celery/Redis optional)
=================================================
Currently uses asyncio.gather + FastAPI BackgroundTasks for in-process concurrency.
To scale to multiple workers, install Redis and Celery (commented out below).

Quick setup for production:
    pip install celery[redis] redis
    redis-server &
    celery -A app.tasks worker --loglevel=info

Enable by uncommenting the Celery sections below and setting REDIS_URL in .env
"""

import asyncio
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

# ============================================================
# In-process background task queue (no Redis needed)
# ============================================================

_task_queue = asyncio.Queue()


async def run_background(coro_fn: Callable, *args, **kwargs) -> None:
    """
    Fire-and-forget: schedule an async coroutine to run in the background.
    Does not block the caller.
    """
    async def _wrapper():
        try:
            await coro_fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Background task error [{coro_fn.__name__}]: {e}")

    asyncio.create_task(_wrapper())


# ============================================================
# Common background task definitions
# ============================================================

async def prefetch_lyrics(video_id: str, title: str, artist: str, language: str, db) -> None:
    """Pre-warm lyrics cache for a track after it starts playing."""
    from app.services.lyrics_service import get_lyrics
    from datetime import datetime, timezone

    if db is None:
        return

    cache_id = f"{video_id}_{language.lower()}" if language else video_id
    existing = await db.lyrics_cache.find_one({"_id": cache_id})
    if existing:
        return  # Already cached

    result = await get_lyrics(track_name=title, artist_name=artist, language=language)
    if result:
        try:
            await db.lyrics_cache.update_one(
                {"_id": cache_id},
                {"$set": {**result, "cached_at": datetime.now(timezone.utc)}},
                upsert=True,
            )
            logger.info(f"🎤 Pre-warmed lyrics cache for {video_id} ({language})")
        except Exception as e:
            logger.debug(f"Lyrics prefetch cache write failed: {e}")


async def warm_artist_cache(artist_name: str, language: str, db) -> None:
    """Pre-warm song cache for an artist's top tracks in a given language."""
    from app.services.youtube_service import search_youtube

    query = f"{artist_name} {language} songs".strip()
    try:
        tracks = await search_youtube(query, max_results=10)
        logger.info(f"🎸 Pre-warmed {len(tracks)} tracks for artist '{artist_name}' ({language})")
    except Exception as e:
        logger.debug(f"Artist cache warm failed for {artist_name}: {e}")


# ============================================================
# Optional: Celery Integration (uncomment to enable)
# ============================================================
# import os
# from celery import Celery
#
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# celery_app = Celery("wave", broker=REDIS_URL, backend=REDIS_URL)
# celery_app.conf.update(
#     task_serializer="json",
#     result_serializer="json",
#     accept_content=["json"],
#     timezone="UTC",
#     enable_utc=True,
# )
#
# @celery_app.task(name="wave.prefetch_lyrics")
# def celery_prefetch_lyrics(video_id, title, artist, language):
#     import asyncio
#     asyncio.run(prefetch_lyrics(video_id, title, artist, language, db=None))
#
# @celery_app.task(name="wave.warm_artist_cache")
# def celery_warm_artist_cache(artist_name, language):
#     import asyncio
#     asyncio.run(warm_artist_cache(artist_name, language, db=None))
