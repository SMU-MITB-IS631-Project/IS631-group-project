"""
Run script for CardTrack Backend API

Usage:
    python run.py
"""
import os
import subprocess
import sys
from pathlib import Path

import uvicorn


def run_migrations() -> None:
    """Apply Alembic migrations before starting the API server."""
    backend_dir = Path(__file__).resolve().parent
    env = os.environ.copy()
    db_url = env.get("DATABASE_URL")
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    if db_url:
        # Pass the application database URL through to Alembic so it
        # can target the same database as the API.
        cmd.extend(["-x", f"db_url={db_url}"])
    subprocess.run(
        cmd,
        cwd=backend_dir,
        env=env,
        check=True,
    )

if __name__ == "__main__":
    run_migrations()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    )
