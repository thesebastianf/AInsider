"""
AInsider Tracker – Database Backup Service
Creates pg_dump backups, retains last 3, stores them in /app/data/backups.
The /app/data directory is exposed as a host bind mount in docker-compose.yml.
"""

import gzip
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("ainsider.backup")

BACKUP_DIR = Path("/app/data/backups")
MAX_BACKUPS = 3


def _ensure_backup_dir():
    """Create backup directory if it doesn't exist."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _rotate_old_backups():
    """Remove oldest backups if we are at or over the limit."""
    backups = sorted(
        BACKUP_DIR.glob("ainsider_db_*.sql.gz"),
        key=lambda p: p.stat().st_mtime
    )
    while len(backups) >= MAX_BACKUPS:
        oldest = backups.pop(0)
        oldest.unlink()
        logger.info(f"Backup rotation: removed {oldest.name}")


def run_backup() -> dict:
    """
    Execute pg_dump and write a gzip-compressed backup to BACKUP_DIR.
    Returns a dict with status, filename, and size_bytes.
    """
    from app.routers.system import add_log

    _ensure_backup_dir()
    _rotate_old_backups()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ainsider_db_{timestamp}.sql.gz"
    dest_path = BACKUP_DIR / filename

    # Parse DATABASE_URL: postgresql://user:password@host:port/dbname
    db_url = os.environ.get("DATABASE_URL", "")
    try:
        rest = db_url.replace("postgresql://", "").replace("postgres://", "")
        userpass, hostdb = rest.split("@", 1)
        user, password = userpass.split(":", 1)
        hostport, dbname = hostdb.rsplit("/", 1)
        host, port = (hostport.split(":", 1) + ["5432"])[:2]
    except Exception as e:
        msg = f"Backup failed: could not parse DATABASE_URL: {e}"
        logger.error(msg)
        add_log("ERROR", msg)
        return {"status": "error", "message": msg}

    env = {**os.environ, "PGPASSWORD": password}
    cmd = ["pg_dump", "-h", host, "-p", port, "-U", user, "-d", dbname,
           "--format=plain", "--no-password"]

    try:
        logger.info(f"Starting database backup: {filename}")
        add_log("INFO", f"Database backup starting: {filename}")

        result = subprocess.run(cmd, env=env, capture_output=True, timeout=120)

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")[:300]
            msg = f"pg_dump failed (exit {result.returncode}): {err}"
            logger.error(msg)
            add_log("ERROR", msg)
            return {"status": "error", "message": msg}

        # Compress with gzip
        with gzip.open(dest_path, "wb") as gz:
            gz.write(result.stdout)

        size_bytes = dest_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        msg = f"Backup complete: {filename} ({size_mb:.2f} MB)"
        logger.info(msg)
        add_log("INFO", msg)

        return {
            "status": "success",
            "filename": filename,
            "path": str(dest_path),
            "size_bytes": size_bytes,
            "timestamp": timestamp,
        }

    except subprocess.TimeoutExpired:
        msg = "Backup failed: pg_dump timed out after 120 seconds"
        logger.error(msg)
        add_log("ERROR", msg)
        if dest_path.exists():
            dest_path.unlink()
        return {"status": "error", "message": msg}

    except FileNotFoundError:
        msg = "Backup failed: pg_dump binary not found in container."
        logger.error(msg)
        add_log("ERROR", msg)
        return {"status": "error", "message": msg}

    except Exception as e:
        msg = f"Backup failed: {e}"
        logger.error(msg)
        add_log("ERROR", msg)
        if dest_path.exists():
            dest_path.unlink()
        return {"status": "error", "message": msg}


def list_backups() -> list[dict]:
    """Return metadata for all existing backup files, newest first."""
    _ensure_backup_dir()
    backups = []
    for p in sorted(BACKUP_DIR.glob("ainsider_db_*.sql.gz"), reverse=True):
        stat = p.stat()
        backups.append({
            "filename": p.name,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return backups
