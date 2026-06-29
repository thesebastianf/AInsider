"""
AInsider Tracker – FastAPI Application Entry Point
Serves React frontend as static files + API endpoints.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import SessionLocal

# ─── Logging Setup ────────────────────────────────────────────
import os
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if settings.DEBUG_MODE:
    # Use Docker mount if exists, else project local
    log_dir = Path("/app/logs") if Path("/app").exists() else Path(__file__).parent.parent.parent / "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_dir / "ainsider_debug.log",
        maxBytes=10*1024*1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    file_handler.setLevel(logging.DEBUG)
    
    # Add handler to root logger so we capture everything
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.DEBUG)

logger = logging.getLogger("ainsider")

# Path to built frontend assets
STATIC_DIR = Path(__file__).parent.parent / "static"


# ─── Lifespan (startup / shutdown) ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.routers.system import add_log

    logger.info("╔══════════════════════════════════════╗")
    logger.info("║   AInsider Tracker – Starting Up     ║")
    logger.info("╚══════════════════════════════════════╝")
    add_log("INFO", "AInsider Tracker starting up...")

    # Seed database if empty
    try:
        db = SessionLocal()
        from app.seed.seeder import seed_database
        seeded = seed_database(db)
        if seeded:
            add_log("INFO", "Database seeded with demo data")
        db.close()
    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        add_log("ERROR", f"Database seeding failed: {str(e)[:100]}")

    # Start background scheduler
    try:
        from app.tasks.scheduler import start_scheduler
        start_scheduler()
        add_log("INFO", "Background scheduler started")
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")
        add_log("ERROR", f"Scheduler start failed: {str(e)[:100]}")

    add_log("INFO", "AInsider Tracker is ready! 🚀")

    yield

    logger.info("AInsider Tracker shutting down...")
    try:
        from app.tasks.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


# ─── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="AInsider Tracker",
    description="Track congressional, senate, and insider stock trades with AI evaluation.",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS Middleware ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Mount API Routers ───────────────────────────────────────
from app.routers import trades, persons, performance, settings as settings_router
from app.routers import system, subscriptions

app.include_router(trades.router)
app.include_router(persons.router)
app.include_router(performance.router)
app.include_router(settings_router.router)
app.include_router(system.router)
app.include_router(subscriptions.router)


# ─── Serve Frontend Static Files ──────────────────────────────
if STATIC_DIR.exists():
    # Mount static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

# ─── Serve User-Uploaded Photos ────────────────────────────────
from pathlib import Path as _Path
_UPLOAD_DIR = _Path("/app/uploads") if _Path("/app").exists() else _Path(__file__).parent.parent.parent / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_UPLOAD_DIR)), name="uploads")

# SPA fallback: serve index.html for all non-API routes
if STATIC_DIR.exists():
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for any non-API route."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))

