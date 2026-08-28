"""
Wave - Recommendations & Trending Routes
"""

from fastapi import APIRouter, Depends, Query
from app.services.recommendation_service import (
    get_trending_tracks,
    get_home_feed,
    get_next_recommendation,
    record_co_listen,
    CATEGORIES,
)
from app.utils.security import get_optional_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])


@router.get("/categories", summary="Get music categories")
async def list_categories():
    """Get browse categories."""
    return {"categories": CATEGORIES}


@router.get("/trending", summary="Get trending tracks")
async def trending(
    category: str = Query("trending", description="Category ID"),
    limit: int = Query(15, ge=1, le=30),
    user=Depends(get_optional_user),
):
    """Get trending tracks for a category."""
    tracks = await get_trending_tracks(category, limit)
    return {"category": category, "tracks": tracks, "total": len(tracks)}


@router.get("/feed", summary="Get home feed")
async def feed(user=Depends(get_optional_user)):
    """Get multi-section home feed."""
    return await get_home_feed()


@router.get("/next", summary="Get next recommended song")
async def next_song(
    current_id: str = Query(..., description="Currently playing video ID"),
    user=Depends(get_optional_user),
):
    """Get the next recommended song based on the current track."""
    track = await get_next_recommendation(current_id)
    return {"track": track}


@router.post("/transition", summary="Record track transition")
async def transition(
    from_id: str = Query(..., description="Previous track video ID"),
    to_id: str = Query(..., description="Next track video ID"),
    user=Depends(get_optional_user),
):
    """Record that a user transitioned from track A to track B to build the graph."""
    await record_co_listen(from_id, to_id)
    return {"status": "recorded"}
