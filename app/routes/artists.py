"""
Wave - Artists API Routes
Provides featured artists, artist profiles, top tracks, and artist search.
"""

from fastapi import APIRouter, HTTPException, Query
from app.services import youtube_service
from app.database import database
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/artists", tags=["Artists"])

# Curated Popular Artists across Telugu, Hindi, English, Tamil, Punjabi
FEATURED_ARTISTS = [
    {
        "id": "arijit-singh",
        "name": "Arijit Singh",
        "genre": "Bollywood / Romantic",
        "image": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=300&h=300&fit=crop&crop=faces",
        "language": "Hindi",
    },
    {
        "id": "sid-sriram",
        "name": "Sid Sriram",
        "genre": "Telugu / Tamil Melodies",
        "image": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=300&h=300&fit=crop&crop=faces",
        "language": "Telugu",
    },
    {
        "id": "anirudh-ravichander",
        "name": "Anirudh Ravichander",
        "genre": "Rock / Electronic / Tamil",
        "image": "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=300&h=300&fit=crop&crop=faces",
        "language": "Tamil",
    },
    {
        "id": "ar-rahman",
        "name": "A.R. Rahman",
        "genre": "World / Classical / Film",
        "image": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=300&h=300&fit=crop&crop=faces",
        "language": "Multilingual",
    },
    {
        "id": "shreya-ghoshal",
        "name": "Shreya Ghoshal",
        "genre": "Melody / Classical",
        "image": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=300&h=300&fit=crop&crop=faces",
        "language": "Multilingual",
    },
    {
        "id": "taylor-swift",
        "name": "Taylor Swift",
        "genre": "Pop / Country",
        "image": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=300&h=300&fit=crop&crop=faces",
        "language": "English",
    },
    {
        "id": "spb",
        "name": "S.P. Balasubrahmanyam",
        "genre": "Legendary Classics",
        "image": "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=300&h=300&fit=crop&crop=faces",
        "language": "Telugu",
    },
    {
        "id": "diljit-dosanjh",
        "name": "Diljit Dosanjh",
        "genre": "Punjabi Pop / Folk",
        "image": "https://images.unsplash.com/photo-1501386761578-eac5c94b800a?w=300&h=300&fit=crop&crop=faces",
        "language": "Punjabi",
    },
    {
        "id": "the-weeknd",
        "name": "The Weeknd",
        "genre": "R&B / Synthwave",
        "image": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=300&h=300&fit=crop&crop=faces",
        "language": "English",
    },
    {
        "id": "devi-sri-prasad",
        "name": "Devi Sri Prasad",
        "genre": "High Voltage Beats / Telugu",
        "image": "https://images.unsplash.com/photo-1465847899084-d164df4dedc6?w=300&h=300&fit=crop&crop=faces",
        "language": "Telugu",
    },
]


@router.get("/featured", response_model=List[dict])
async def get_featured_artists():
    """Get curated list of popular artists."""
    return FEATURED_ARTISTS


@router.get("/{artist_name}")
async def get_artist_profile(
    artist_name: str,
    limit: int = Query(default=30, ge=5, le=50),
):
    """
    Get artist profile and top hit tracks.
    Searches YouTube and caches in MongoDB for blazing fast subsequent loads.
    """
    if not artist_name or len(artist_name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Artist name is required")

    artist_clean = artist_name.strip()

    # Match featured artist image if available
    matched_image = ""
    matched_genre = "Popular Artist"
    for a in FEATURED_ARTISTS:
        if a["name"].lower() == artist_clean.lower() or a["id"] == artist_clean.lower().replace(" ", "-"):
            matched_image = a["image"]
            matched_genre = a["genre"]
            artist_clean = a["name"]
            break

    # Cache key
    cache_key = f"artist_tracks_{artist_clean.lower()}"
    if database.db is not None:
        cached = await database.db.cache.find_one({"key": cache_key})
        if cached and "tracks" in cached and len(cached["tracks"]) > 0:
            return {
                "artist": artist_clean,
                "genre": matched_genre,
                "image": matched_image or (cached["tracks"][0].get("thumbnail") if cached["tracks"] else ""),
                "total_tracks": len(cached["tracks"]),
                "tracks": cached["tracks"],
            }

    # Fetch top songs for the artist
    search_queries = [
        f"{artist_clean} top hit songs jukebox",
        f"{artist_clean} best songs",
        f"{artist_clean} all songs",
    ]

    tracks = []
    seen = set()

    for q in search_queries[:2]:
        results = await youtube_service.search_youtube(q, max_results=limit)
        for r in results:
            vid = r.get("video_id")
            if vid and vid not in seen:
                seen.add(vid)
                r["artist"] = artist_clean
                tracks.append(r)
            if len(tracks) >= limit:
                break
        if len(tracks) >= limit:
            break

    if not matched_image and tracks:
        matched_image = tracks[0].get("thumbnail", "")

    # Cache for 12 hours
    if database.db is not None and tracks:
        await database.db.cache.update_one(
            {"key": cache_key},
            {"$set": {"key": cache_key, "tracks": tracks}},
            upsert=True,
        )

    return {
        "artist": artist_clean,
        "genre": matched_genre,
        "image": matched_image,
        "total_tracks": len(tracks),
        "tracks": tracks,
    }
