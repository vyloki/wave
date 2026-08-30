"""
Wave - Stream Routes
Audio streaming endpoints that proxy YouTube audio through our backend.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from app.services.stream_service import get_cached_stream_url
from app.services.youtube_service import get_stream_url
from app.utils.security import get_optional_user
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["Streaming"])


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@router.get(
    "/{video_id}",
    summary="Stream audio for a video"
)
async def stream_audio(
    video_id: str,
    request: Request,
    user: dict = Depends(get_optional_user),
):
    """
    Stream audio from YouTube through our server with seeking and auto-token recovery.
    """
    # Get the stream URL (cached or fresh)
    stream_url = await get_cached_stream_url(video_id)
    if not stream_url:
        raise HTTPException(
            status_code=404,
            detail="Could not extract audio stream"
        )

    # Forward range headers for seeking support
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    try:
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        response = await client.send(
            client.build_request("GET", stream_url, headers=headers),
            stream=True,
        )

        # If expired YouTube CDN token (403/404/410), refresh stream URL on the fly
        if response.status_code in (403, 404, 410):
            logger.info(f"🔄 Stream URL expired (HTTP {response.status_code}) for {video_id}, extracting fresh stream...")
            await response.aclose()
            fresh_info = await get_stream_url(video_id)
            if fresh_info and fresh_info.get("url"):
                stream_url = fresh_info["url"]
                response = await client.send(
                    client.build_request("GET", stream_url, headers=headers),
                    stream=True,
                )

        # Determine content type
        content_type = response.headers.get(
            "content-type", "audio/mp4"
        )

        # Build response headers
        response_headers = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }

        # Forward content-related headers
        if "content-length" in response.headers:
            response_headers["Content-Length"] = response.headers[
                "content-length"
            ]
        if "content-range" in response.headers:
            response_headers["Content-Range"] = response.headers[
                "content-range"
            ]

        async def stream_generator():
            """Yield audio data in chunks."""
            try:
                async for chunk in response.aiter_bytes(
                    chunk_size=64 * 1024
                ):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        status_code = response.status_code if response.status_code in (200, 206) else (206 if range_header else 200)

        return StreamingResponse(
            stream_generator(),
            status_code=status_code,
            media_type=content_type,
            headers=response_headers,
        )

    except Exception as e:
        logger.error(f"Stream error for {video_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Audio streaming failed"
        )


@router.get(
    "/{video_id}/info",
    summary="Get stream metadata"
)
async def stream_info(video_id: str):
    """Get metadata about the stream (duration, format, etc.)."""
    info = await get_stream_url(video_id)
    if not info:
        raise HTTPException(
            status_code=404,
            detail="Could not get stream info"
        )
    return {
        "video_id": video_id,
        "available": True,
        "format": info.get("format_note", "audio only"),
        "ext": info.get("ext", "mp4"),
        "duration": info.get("duration", 0),
        "filesize": info.get("filesize"),
    }


@router.get(
    "/{video_id}/download",
    summary="Download audio file"
)
async def download_audio(
    video_id: str,
    title: str = "song",
    artist: str = "artist",
):
    """
    Stream audio with Content-Disposition header so the browser directly downloads it.
    """
    stream_url = await get_cached_stream_url(video_id)
    if not stream_url:
        raise HTTPException(
            status_code=404,
            detail="Could not extract audio stream for download"
        )

    # Sanitize filename
    safe_name = "".join(c for c in f"{artist} - {title}" if c.isalnum() or c in " ._-").strip() or "track"
    filename = f"{safe_name}.mp3"

    try:
        client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        response = await client.send(
            client.build_request("GET", stream_url),
            stream=True,
        )

        content_type = response.headers.get("content-type", "audio/mpeg")

        response_headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        }
        if "content-length" in response.headers:
            response_headers["Content-Length"] = response.headers["content-length"]

        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes(chunk_size=128 * 1024):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_generator(),
            media_type=content_type,
            headers=response_headers,
        )
    except Exception as e:
        logger.error(f"Download stream error for {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Download failed")
