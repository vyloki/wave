"""
Wave - FastAPI Application Entry Point
Main application setup with CORS, static files, lifespan, and route registration.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.database import database
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("wave")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # === STARTUP ===
    logger.info("🎵 Starting Wave Music App...")
    logger.info(f"   Version: {settings.app_version}")
    logger.info(f"   Debug: {settings.debug}")

    # Connect to MongoDB
    await database.connect()

    logger.info(
        f"🚀 Wave is ready at "
        f"http://{settings.host}:{settings.port}"
    )

    yield  # Application is running

    # === SHUTDOWN ===
    logger.info("🛑 Shutting down Wave...")
    await database.disconnect()
    logger.info("👋 Wave stopped gracefully")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="🎵 Wave — Your Personal Music Streaming App",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS Middleware — allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routes ---
from app.routes import auth, search, stream, playlist, history, lyrics, recommendations, artists
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(stream.router)
app.include_router(playlist.router)
app.include_router(history.router)
app.include_router(lyrics.router)
app.include_router(recommendations.router)
app.include_router(artists.router)

# Health check endpoint
@app.get("/api/health", tags=["System"])
async def health_check():
    """Health check endpoint to verify the server and database are running."""
    try:
        # Ping MongoDB to check connection
        await database.client.admin.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "database": db_status,
    }


# --- Static Files & Frontend Serving ---
# Serve the frontend directory as static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.exists(frontend_dir):
    # Serve static assets (CSS, JS, images)
    app.mount(
        "/static",
        StaticFiles(directory=frontend_dir),
        name="static",
    )

    # Serve index.html for the root path (SPA)
    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve the frontend SPA."""
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "🎵 Wave API is running. Frontend not found."}
else:
    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint when frontend is not yet built."""
        return {
            "message": "🎵 Wave API is running",
            "docs": "/docs",
            "health": "/api/health",
        }
