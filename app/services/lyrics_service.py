"""
Wave - Lyrics Service
Multi-tier lyrics search using LRCLIB API with smart title/artist normalization.
Free, no API key needed.
"""

import httpx
import logging
from typing import Optional, List, Dict
import re

logger = logging.getLogger(__name__)
LRCLIB_BASE = "https://lrclib.net/api"

# Record labels / uploaders that should NOT be treated as song artists
RECORD_LABELS = {
    "think music telugu", "think music", "t-series", "tseries", "t-series telugu",
    "t-series regional", "sony music india", "sony music south", "zee music company",
    "zee music south", "aditya music", "saregama music", "saregama", "saregama telugu",
    "lahari music", "speed records", "yrf", "tips official", "geetha arts", "svcc",
    "mythri movie makers", "dvi", "sun nxt", "mangli official", "madhura audio",
    "vel records", "times music", "tips telugu", "aditya music telugu",
}


def clean_song_titles(raw_title: str, raw_artist: str = "") -> List[str]:
    """
    Generate clean candidate search queries from a raw YouTube title and artist.
    Extracts core song names by stripping parenthetical noise, tags, and record labels.
    """
    candidates = []

    # 1. Strip everything inside parentheses (e.g. '(Song)', '(Official Video)', '(From "Movie")')
    no_parens = re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_title)

    # 2. Split by delimiters like |, -, :, /, ~ to isolate song name and movie/singer
    parts = re.split(r'[\|\-:\/•~]', no_parens)
    parts = [p.strip() for p in parts if p.strip()]

    if parts:
        # Candidate A: Just the first part (usually the pure song title, e.g. "MALLEPOOLA PALLAKI")
        p0 = parts[0]
        # Remove any lingering "song", "video" words from the first part
        p0_clean = re.sub(r'\b(song|video|audio|lyrical|lyrics|full)\b', '', p0, flags=re.IGNORECASE).strip()
        if p0_clean:
            candidates.append(p0_clean)

        # Candidate B: First part + Second part (Song + Movie or Song + Singer)
        if len(parts) > 1:
            p1_clean = re.sub(r'\b(song|video|audio|lyrical|lyrics|full|official|hd|4k)\b', '', parts[1], flags=re.IGNORECASE).strip()
            if p0_clean and p1_clean:
                candidates.append(f"{p0_clean} {p1_clean}")

    # 3. If raw artist is a real singer (not a record label), add 'Artist Song' candidate
    artist_clean = raw_artist.strip()
    if artist_clean and artist_clean.lower() not in RECORD_LABELS:
        if candidates:
            candidates.insert(0, f"{candidates[0]} {artist_clean}")

    # 4. Clean general noise words from full raw title
    clean_all = re.sub(r'\b(song|video|audio|lyrical|lyrics|full|hd|4k|official|jukebox|telugu|hindi|tamil|english|punjabi|remix)\b', '', raw_title, flags=re.IGNORECASE)
    clean_all = re.sub(r'[\(\)\[\]\|\-@:\/~•]', ' ', clean_all)
    clean_all = ' '.join(clean_all.split()).strip()
    if clean_all:
        candidates.append(clean_all)

    # Deduplicate while preserving priority order
    seen = set()
    res = []
    for c in candidates:
        norm = ' '.join(c.split()).strip()
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            res.append(norm)

    return res


async def get_lyrics(
    track_name: str,
    artist_name: str = "",
    album_name: str = "",
    duration: int = 0,
) -> Optional[dict]:
    """
    Fetch lyrics from LRCLIB using smart multi-tier query fallback.
    Returns synced or plain lyrics.
    """
    queries = clean_song_titles(track_name, artist_name)
    logger.info(f"🔍 Searching lyrics for '{track_name}' with candidates: {queries}")

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            for q in queries:
                resp = await client.get(
                    f"{LRCLIB_BASE}/search",
                    params={"q": q}
                )

                if resp.status_code == 200:
                    results = resp.json()
                    if results and isinstance(results, list) and len(results) > 0:
                        # Prefer results with synced lyrics
                        best = None
                        for r in results:
                            if r.get("syncedLyrics"):
                                best = r
                                break
                        if not best:
                            best = results[0]

                        parsed = _parse_lyrics_response(best)
                        if parsed and (parsed["synced_lyrics"] or parsed["plain_lyrics"]):
                            logger.info(f"🎤 Lyrics found for '{q}': {best.get('trackName')} by {best.get('artistName')}")
                            return parsed

    except Exception as e:
        logger.warning(f"Lyrics search error for '{track_name}': {e}")

    return None


def _parse_lyrics_response(data: dict) -> dict:
    """Parse LRCLIB response into standardized format."""
    result = {
        "source": "lrclib",
        "synced_lyrics": [],
        "plain_lyrics": "",
        "track_name": data.get("trackName", ""),
        "artist_name": data.get("artistName", ""),
    }

    synced_lrc = data.get("syncedLyrics", "")
    if synced_lrc:
        result["synced_lyrics"] = _parse_lrc(synced_lrc)

    plain = data.get("plainLyrics", "")
    if plain:
        result["plain_lyrics"] = plain

    return result


def _parse_lrc(lrc_text: str) -> List[Dict]:
    """Parse LRC timestamped strings into [{time, text}]."""
    lines = []
    pattern = re.compile(r'\[(\d+):(\d+)(?:\.(\d+))?\](.*)')

    for line in lrc_text.strip().split('\n'):
        match = pattern.match(line.strip())
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            centiseconds = int(match.group(3) or 0)
            text = match.group(4).strip()

            time_seconds = minutes * 60 + seconds + centiseconds / 100.0

            if text:
                lines.append({
                    "time": round(time_seconds, 2),
                    "text": text,
                })

    return lines
