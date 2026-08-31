"""
Wave - Link Audio Extractor Routes
Endpoints for extracting audio from links, streaming, downloading, and managing extraction history.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, Literal
from app.services.extractor_service import (
    extract_from_url,
    get_extraction_history,
    delete_extraction_history,
    clear_extraction_history,
)
from app.database import database
from app.utils.security import get_optional_user
from datetime import datetime, timezone
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extract", tags=["Link Extraction"])


class ExtractRequest(BaseModel):
    url: str
    mode: Literal["same", "original"] = "same"


@router.post("", summary="Extract audio or match full song from URL")
async def extract_audio_endpoint(
    req: ExtractRequest,
    user: Optional[dict] = Depends(get_optional_user),
):
    """
    Extract audio or match original full song from YouTube, Instagram, Twitter/X, TikTok, Reddit, etc.
    Modes:
      - 'same': Extracts exact audio clip of the link.
      - 'original': Searches and matches the full-length studio track.
    """
    user_id = str(user["_id"]) if user and "_id" in user else None
    result = await extract_from_url(req.url, req.mode, user_id)

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Could not extract audio from this link.")
        )

    return result


@router.get("/history", summary="Get link extraction history")
async def get_history_endpoint(
    limit: int = 20,
    user: Optional[dict] = Depends(get_optional_user),
):
    """Get the user's past link extraction history."""
    user_id = str(user["_id"]) if user and "_id" in user else None
    history = await get_extraction_history(user_id, limit)
    return {"history": history, "total": len(history)}


@router.delete("/history/{item_id}", summary="Delete single history item")
async def delete_history_endpoint(
    item_id: str,
    user: Optional[dict] = Depends(get_optional_user),
):
    """Delete a single extraction record from history."""
    user_id = str(user["_id"]) if user and "_id" in user else None
    success = await delete_extraction_history(item_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="History item not found")
    return {"status": "deleted", "id": item_id}


@router.delete("/history", summary="Clear all extraction history")
async def clear_history_endpoint(
    user: Optional[dict] = Depends(get_optional_user),
):
    """Clear all extraction history for the current user."""
    user_id = str(user["_id"]) if user and "_id" in user else None
    await clear_extraction_history(user_id)
    return {"status": "cleared"}


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


from fastapi.responses import StreamingResponse, Response


@router.api_route("/stream/{extraction_id}", methods=["GET", "HEAD"], summary="Stream extracted audio")
async def stream_extracted_audio(
    extraction_id: str,
    request: Request,
):
    """
    Proxy stream extracted audio using cached direct stream URL with Range and HEAD support.
    """
    db = database.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    cached = await db.stream_cache.find_one({"_id": extraction_id})
    if not cached or not cached.get("stream_url"):
        raise HTTPException(status_code=404, detail="Extracted audio stream not found or expired")

    stream_url = cached["stream_url"]

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header
    elif request.method == "HEAD":
        headers["Range"] = "bytes=0-1"

    try:
        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        response = await client.send(
            client.build_request("GET", stream_url, headers=headers),
            stream=True,
        )

        if response.status_code >= 400:
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=response.status_code, detail="Extracted stream source error")

        content_type = response.headers.get("content-type", "audio/mp4")
        if content_type.startswith("video/"):
            content_type = content_type.replace("video/", "audio/")
        elif not content_type.startswith("audio/"):
            content_type = "audio/mp4"

        response_headers = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        }
        if "content-length" in response.headers:
            response_headers["Content-Length"] = response.headers["content-length"]
        if "content-range" in response.headers:
            response_headers["Content-Range"] = response.headers["content-range"]

        if request.method == "HEAD":
            await response.aclose()
            await client.aclose()
            return Response(
                status_code=200 if not range_header else 206,
                headers=response_headers,
                media_type=content_type,
            )

        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream error for {extraction_id}: {e}")
        raise HTTPException(status_code=500, detail="Audio streaming failed")


@router.get("/download/{extraction_id}", summary="Download extracted audio")
async def download_extracted_audio(
    extraction_id: str,
    title: str = "extracted_song",
    artist: str = "artist",
):
    """
    Download extracted audio file as an MP3 attachment.
    """
    db = database.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    cached = await db.stream_cache.find_one({"_id": extraction_id})
    if not cached or not cached.get("stream_url"):
        raise HTTPException(status_code=404, detail="Extracted audio not found for download")

    stream_url = cached["stream_url"]
    safe_name = "".join(c for c in f"{artist} - {title}" if c.isalnum() or c in " ._-").strip() or "extracted_song"
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
        logger.error(f"Download error for {extraction_id}: {e}")
        raise HTTPException(status_code=500, detail="Download failed")
