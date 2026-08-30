"""
Wave - Lyrics Service
Multi-tier lyrics search using LRCLIB API with smart title/artist normalization
and automatic Indic-to-English (Romanized/English spelling) transliteration.
Free, no API key needed.
"""

import httpx
import logging
from typing import Optional, List, Dict
import re
from app.utils.transliterator import transliterate_indic_to_english

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

# Language hints for scoring LRCLIB results
LANG_LABEL_HINTS = {
    "Telugu": ["telugu", "think music telugu", "aditya music", "lahari", "madhura",
               "mango music", "saregama telugu", "aditya music telugu"],
    "Tamil": ["tamil", "think music india", "think music tamil", "sun pictures",
              "divo", "u1 records", "sony music south", "saregama tamil", "behindwoods"],
    "Hindi": ["hindi", "t-series", "zee music", "yrf", "eros now", "saregama music",
              "sony music india", "tips official"],
    "Malayalam": ["malayalam", "muzik247", "123musix", "goodwill", "saregama malayalam"],
    "Kannada": ["kannada", "anand audio", "jhankar", "a2 music"],
    "Punjabi": ["punjabi", "speed records", "apna punjab", "geet mp3"],
    "English": ["english"],
}

# Labels exclusively tied to a specific language — strong negative signal for others
LANG_EXCLUSIVE_LABELS = {
    "Tamil": ["think music tamil", "divo music", "u1 records", "sun pictures"],
    "Telugu": ["aditya music", "lahari music", "madhura audio", "mango music telugu"],
    "Hindi": ["t-series", "zee music company", "yrf"],
}


def _score_result_for_language(result: dict, language: str) -> int:
    """
    Score a LRCLIB result based on how well it matches the target language.
    Higher is better.
    """
    if not language:
        return 0

    artist_name = (result.get("artistName") or "").lower()
    track_name = (result.get("trackName") or "").lower()
    album_name = (result.get("albumName") or "").lower()
    plain = (result.get("plainLyrics") or "").lower()
    combined = f"{artist_name} {track_name} {album_name}"

    score = 0
    hints = LANG_LABEL_HINTS.get(language, [])

    for hint in hints:
        if hint in combined:
            score += 12
            break

    # If looking for Telugu, check if plain lyrics contain Telugu Unicode
    if language.lower() == "telugu":
        if any('\u0C00' <= ch <= '\u0C7F' for ch in (result.get("plainLyrics") or "")):
            score += 20
        # Penalize Tamil unicode if Telugu requested
        if any('\u0B80' <= ch <= '\u0BFF' for ch in (result.get("plainLyrics") or "")):
            score -= 25

    for lang, hint_list in LANG_LABEL_HINTS.items():
        if lang.lower() == language.lower():
            continue
        for hint in hint_list:
            if hint in combined:
                score -= 10
                break

    for lang, labels in LANG_EXCLUSIVE_LABELS.items():
        if lang.lower() == language.lower():
            continue
        for label in labels:
            if label in combined:
                score -= 18
                break

    return score


def clean_song_titles(raw_title: str, raw_artist: str = "") -> List[str]:
    """
    Generate clean candidate search queries from a raw YouTube title and artist.
    Extracts core song names by stripping parenthetical noise, tags, and record labels.
    """
    candidates = []

    # 1. Strip everything inside parentheses
    no_parens = re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_title)

    # 2. Split by delimiters
    parts = re.split(r'[\|\-:\/•~]', no_parens)
    parts = [p.strip() for p in parts if p.strip()]

    if parts:
        p0 = parts[0]
        p0_clean = re.sub(r'\b(song|video|audio|lyrical|lyrics|full)\b', '', p0, flags=re.IGNORECASE).strip()
        if p0_clean:
            candidates.append(p0_clean)

        if len(parts) > 1:
            p1_clean = re.sub(r'\b(song|video|audio|lyrical|lyrics|full|official|hd|4k)\b', '', parts[1], flags=re.IGNORECASE).strip()
            if p0_clean and p1_clean:
                candidates.append(f"{p0_clean} {p1_clean}")

    artist_clean = raw_artist.strip()
    if artist_clean and artist_clean.lower() not in RECORD_LABELS:
        if candidates:
            candidates.insert(0, f"{candidates[0]} {artist_clean}")

    clean_all = re.sub(r'\b(song|video|audio|lyrical|lyrics|full|hd|4k|official|jukebox|telugu|hindi|tamil|english|punjabi|remix)\b', '', raw_title, flags=re.IGNORECASE)
    clean_all = re.sub(r'[\(\)\[\]\|\-@:\/~•]', ' ', clean_all)
    clean_all = ' '.join(clean_all.split()).strip()
    if clean_all:
        candidates.append(clean_all)

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
    language: str = "",
) -> Optional[dict]:
    """
    Fetch lyrics from LRCLIB using smart multi-tier query fallback.
    Language-aware: prefers results matching the target language.
    Automatically transliterates Telugu/Indic lyrics to English spelling.
    """
    queries = clean_song_titles(track_name, artist_name)
    logger.info(f"🔍 Searching lyrics for '{track_name}' (lang={language!r}) with candidates: {queries}")

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
                        # Score all results by language match
                        scored = []
                        for r in results:
                            lang_score = _score_result_for_language(r, language)
                            has_synced = bool(r.get("syncedLyrics"))
                            scored.append((lang_score, has_synced, r))

                        # Sort: highest language score first, then prefer synced
                        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

                        for lang_score, has_synced, r in scored:
                            parsed = _parse_lyrics_response(r)
                            if parsed and (parsed["synced_lyrics"] or parsed["plain_lyrics"]):
                                logger.info(
                                    f"🎤 Lyrics found for '{q}' (score={lang_score}): "
                                    f"{r.get('trackName')} by {r.get('artistName')}"
                                )
                                return parsed

    except Exception as e:
        logger.warning(f"Lyrics search error for '{track_name}': {e}")

    return None


def _parse_lyrics_response(data: dict) -> dict:
    """Parse LRCLIB response into standardized format with English transliteration."""
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
        # Transliterate Indic scripts to English spelling
        result["plain_lyrics"] = transliterate_indic_to_english(plain)

    return result


def _parse_lrc(lrc_text: str) -> List[Dict]:
    """Parse LRC timestamped strings into [{time, text}] with English transliteration."""
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
                # Transliterate Telugu/Indic words to English spelling
                romanized_text = transliterate_indic_to_english(text)
                lines.append({
                    "time": round(time_seconds, 2),
                    "text": romanized_text,
                })

    return lines
