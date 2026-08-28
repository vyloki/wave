#!/usr/bin/env python3
"""
Wave — Quick Start Script
Run this to start the Wave music app server.

Usage:
    python run.py
"""

import uvicorn
from app.config import settings


def main():
    """Start the Wave server."""
    print()
    print("  🎵  W A V E  ")
    print("  ─────────────────────────")
    print("  Your Personal Music App")
    print(f"  Version {settings.app_version}")
    print()
    print(f"  🌐  http://localhost:{settings.port}")
    print(f"  📚  http://localhost:{settings.port}/docs")
    print()

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    main()
