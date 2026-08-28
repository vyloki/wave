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
    Stream audio from YouTube through our server.

    This endpoint proxies the audio stream, which:
    1. Avoids CORS issues in the browser
    2. Hides the YouTube URL from the client
    3. Supports range requests for seeking

    The audio is streamed in chunks — not downloaded fully first.
    """
    # Get the stream URL (cached or fresh)
    stream_url = await get_cached_stream_url(video_id)
    if not stream_url:
        raise HTTPException(
            status_code=404,
            detail="Could not extract audio stream"
        )

    # Forward range headers for seeking support
    headers = {}
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    try:
        # Stream the audio through our server
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
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

        status_code = 206 if range_header else 200

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
