"""
Wave - Recommendation Engine & Trending Service
Provides curated trending feeds, genre categories, and graph-based next-track recommendations.
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from app.database import database
from app.services.youtube_service import search_youtube, get_related_videos
import logging
import asyncio

logger = logging.getLogger(__name__)

# Predefined categories for quick browsing
CATEGORIES = [
    {"id": "trending", "name": "Trending Hits", "query": "Top trending songs 2025 official audio", "icon": "flame"},
    {"id": "telugu", "name": "Telugu Hits", "query": "Latest Telugu hit songs jukebox", "icon": "music-2"},
    {"id": "hindi", "name": "Bollywood Top", "query": "Top Bollywood romantic songs 2025", "icon": "sparkles"},
    {"id": "english", "name": "Global Pop", "query": "Billboard top hits pop songs", "icon": "globe"},
    {"id": "punjabi", "name": "Punjabi Beats", "query": "Top trending Punjabi songs", "icon": "zap"},
    {"id": "tamil", "name": "Tamil Hits", "query": "Latest Tamil blockbuster songs", "icon": "disc"},
    {"id": "lofi", "name": "Chill & Lo-Fi", "query": "Chill lofi hip hop beats to study relax to", "icon": "coffee"},
    {"id": "rock", "name": "Rock & Indie", "query": "Indie rock top tracks", "icon": "guitar"},
]


async def get_trending_tracks(category: str = "trending", limit: int = 15) -> List[dict]:
    """Get trending tracks for a given category with MongoDB caching."""
    db = database.db
    cache_key = f"feed:{category}:{limit}"

    if db is not None:
        try:
            cached = await db.recommendation_cache.find_one({
                "_id": cache_key,
                "cached_at": {"$gt": datetime.now(timezone.utc) - timedelta(hours=6)}
            })
            if cached and cached.get("tracks"):
                return cached["tracks"]
        except Exception as e:
            logger.warning(f"Feed cache lookup error: {e}")

    # Find the query for this category
    cat_info = next((c for c in CATEGORIES if c["id"] == category), CATEGORIES[0])
    query = cat_info["query"]

    # Search YouTube
    tracks = await search_youtube(query, max_results=limit)

    # Cache results in DB
    if db is not None and tracks:
        try:
            await db.recommendation_cache.update_one(
                {"_id": cache_key},
                {
                    "$set": {
                        "category": category,
                        "tracks": tracks,
                        "cached_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Feed cache save error: {e}")

    return tracks


async def get_home_feed() -> Dict[str, List[dict]]:
    """Fetch sections for the home feed."""
    trending_task = get_trending_tracks("trending", 10)
    telugu_task = get_trending_tracks("telugu", 10)
    hindi_task = get_trending_tracks("hindi", 10)
    english_task = get_trending_tracks("english", 10)
    lofi_task = get_trending_tracks("lofi", 10)

    results = await asyncio.gather(
        trending_task,
        telugu_task,
        hindi_task,
        english_task,
        lofi_task,
        return_exceptions=True
    )

    feed = {
        "trending": results[0] if isinstance(results[0], list) else [],
        "telugu": results[1] if isinstance(results[1], list) else [],
        "hindi": results[2] if isinstance(results[2], list) else [],
        "english": results[3] if isinstance(results[3], list) else [],
        "lofi": results[4] if isinstance(results[4], list) else [],
        "categories": CATEGORIES,
    }
    return feed


async def record_co_listen(track_a_id: str, track_b_id: str) -> None:
    """Update the recommendation graph when tracks are played in sequence."""
    if not track_a_id or not track_b_id or track_a_id == track_b_id:
        return

    db = database.db
    if db is None:
        return

    try:
        # Increment edge weight from A -> B
        await db.recommendation_graph.update_one(
            {"track_id": track_a_id, "edges.target": track_b_id},
            {"$inc": {"edges.$.weight": 1.0}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        )
        # If edge didn't exist, push it
        res = await db.recommendation_graph.update_one(
            {"track_id": track_a_id, "edges.target": {"$ne": track_b_id}},
            {
                "$push": {"edges": {"target": track_b_id, "weight": 1.0, "type": "co-listen"}},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )
    except Exception as e:
        logger.debug(f"Graph update error: {e}")


async def get_next_recommendation(current_video_id: str) -> Optional[dict]:
    """
    Get the next song to play using graph co-listening data,
    falling back to YouTube related videos.
    """
    db = database.db

    # 1. Try Graph-based co-listening
    if db is not None:
        try:
            node = await db.recommendation_graph.find_one({"track_id": current_video_id})
            if node and node.get("edges"):
                sorted_edges = sorted(node["edges"], key=lambda x: x.get("weight", 0), reverse=True)
                top_target_id = sorted_edges[0]["target"]
                target_track = await db.song_cache.find_one({"_id": top_target_id})
                if target_track:
                    target_track.pop("_id", None)
                    target_track["video_id"] = top_target_id
                    return target_track
        except Exception as e:
            logger.debug(f"Graph recommendation error: {e}")

    # 2. Fallback to YouTube related
    related = await get_related_videos(current_video_id, max_results=5)
    if related:
        return related[0]

    return None
