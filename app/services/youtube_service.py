"""
Wave - YouTube Service
Search YouTube for songs and extract audio metadata & stream URLs using yt-dlp.
"""

import yt_dlp
import asyncio
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone
import re

logger = logging.getLogger(__name__)

# yt-dlp options for fast flat search
SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "skip_download": True,
    "ignoreerrors": True,
    "no_color": True,
}

# yt-dlp options for stream URL extraction
STREAM_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "format": "bestaudio/best",
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "ios", "web"]
        }
    },
    "ignoreerrors": True,
    "no_color": True,
}


def _clean_title_and_artist(raw_title: str, uploader: str) -> tuple[str, str]:
    """Parse title and artist from raw title and uploader."""
    clean_title = raw_title
    artist = uploader or "Unknown Artist"

    # Remove common video tags
    clean_title = re.sub(
        r'(\(Official\s*(Music\s*)?Video\)|\[Official\s*(Music\s*)?Video\]|\(Official\s*Audio\)|\[Official\s*Audio\]|\(Lyric\s*Video\)|\[Lyric\s*Video\]|\(Audio\)|\[Audio\]|\(Visualizer\)|\[Visualizer\]|\(Video\)|\[Video\])',
        '',
        clean_title,
        flags=re.IGNORECASE
    ).strip()

    # Check for "Artist - Title" format
    if " - " in clean_title:
        parts = clean_title.split(" - ", 1)
        artist_candidate = parts[0].strip()
        title_candidate = parts[1].strip()
        if artist_candidate and title_candidate:
            return title_candidate, artist_candidate

    # Check for "Artist | Title" format
    if " | " in clean_title:
        parts = clean_title.split(" | ", 1)
        title_candidate = parts[0].strip()
        artist_candidate = parts[1].strip()
        if title_candidate:
            return title_candidate, uploader or artist_candidate

    # Clean uploader name (remove " - Topic", "VEVO", etc.)
    if artist.endswith(" - Topic"):
        artist = artist.replace(" - Topic", "")
    if artist.endswith("VEVO"):
        artist = artist.replace("VEVO", "")

    return clean_title, artist


def _extract_track_from_entry(entry: dict) -> Optional[dict]:
    """Extract standard track dictionary from a flat or detailed yt-dlp entry."""
    if not entry:
        return None

    video_id = entry.get("id") or entry.get("url")
    if not video_id:
        return None

    # Strip full URL if id is a url
    if "youtube.com" in video_id or "youtu.be" in video_id:
        match = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11})', video_id)
        if match:
            video_id = match.group(1)
        else:
            return None

    raw_title = entry.get("title") or "Unknown Song"
    uploader = entry.get("uploader") or entry.get("channel") or ""

    clean_title, artist = _clean_title_and_artist(raw_title, uploader)

    # Get thumbnail
    thumbnail = ""
    thumbnails = entry.get("thumbnails", [])
    if thumbnails and isinstance(thumbnails, list):
        # Grab the highest resolution or last thumbnail
        for t in reversed(thumbnails):
            if isinstance(t, dict) and t.get("url"):
                thumbnail = t["url"]
                break

    if not thumbnail:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    duration = int(entry.get("duration") or 0)

    return {
        "video_id": video_id,
        "title": raw_title,
        "track_name": clean_title,
        "artist": artist,
        "album": entry.get("album") or "",
        "duration": duration,
        "thumbnail": thumbnail,
        "view_count": entry.get("view_count") or 0,
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        "source": "youtube",
    }


async def search_youtube(
    query: str,
    max_results: int = 20
) -> List[dict]:
    """
    Search YouTube for songs matching the query.
    Returns a list of track info dictionaries.
    """
    def _search():
        results = []
        search_query = f"ytsearch{max_results}:{query}"

        try:
            with yt_dlp.YoutubeDL(SEARCH_OPTS) as ydl:
                info = ydl.extract_info(search_query, download=False)
                if info and "entries" in info:
                    for entry in info["entries"]:
                        track = _extract_track_from_entry(entry)
                        if track and track["video_id"]:
                            results.append(track)
        except Exception as e:
            logger.error(f"YouTube search error for '{query}': {e}")

        return results

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _search)

    logger.info(f"🔍 YouTube search '{query}': {len(results)} results")
    return results


async def get_video_info(video_id: str) -> Optional[dict]:
    """Get detailed info for a specific YouTube video."""
    def _get_info():
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "ignoreerrors": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return _extract_track_from_entry(info)
        except Exception as e:
            logger.error(f"Video info error for {video_id}: {e}")
        return None

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_info)


async def get_stream_url(video_id: str) -> Optional[dict]:
    """
    Extract the direct audio stream URL for a YouTube video using Android/iOS/Web clients.
    """
    def _extract():
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with yt_dlp.YoutubeDL(STREAM_OPTS) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    stream_url = info.get("url")
                    if stream_url:
                        return {
                            "url": stream_url,
                            "format": info.get("format", ""),
                            "ext": info.get("ext", "mp4"),
                            "filesize": info.get("filesize"),
                            "duration": int(info.get("duration") or 0),
                            "title": info.get("title", ""),
                            "expires_at": datetime.now(timezone.utc),
                        }
        except Exception as e:
            logger.error(f"Stream extraction error for {video_id}: {e}")
        return None

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _extract)

    if result:
        logger.info(f"🎶 Stream URL extracted for {video_id} ({result.get('ext')})")
    else:
        logger.warning(f"⚠️ Failed to extract stream for {video_id}")

    return result


async def get_youtube_suggestions(query: str) -> List[str]:
    """Get YouTube search autocomplete suggestions."""
    import httpx
    import json

    try:
        url = "https://suggestqueries-clients6.youtube.com/complete/search"
        params = {
            "client": "youtube",
            "q": query,
            "ds": "yt",
        }
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                text = resp.text
                start = text.index("(") + 1
                end = text.rindex(")")
                data = json.loads(text[start:end])
                if data and len(data) > 1 and isinstance(data[1], list):
                    suggestions = [item[0] for item in data[1] if item and isinstance(item, list)]
                    return suggestions[:8]
    except Exception as e:
        logger.warning(f"Suggestions error for '{query}': {e}")

    return []


async def get_related_videos(video_id: str, max_results: int = 10) -> List[dict]:
    """Get related/recommended tracks for a given video."""
    def _get_related():
        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "ignoreerrors": True,
        }
        results = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    related = info.get("related_videos", []) or []
                    for entry in related[:max_results]:
                        track = _extract_track_from_entry(entry)
                        if track and track["video_id"]:
                            track["source"] = "youtube_related"
                            results.append(track)
        except Exception as e:
            logger.warning(f"Related videos error for {video_id}: {e}")

        return results

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_related)
