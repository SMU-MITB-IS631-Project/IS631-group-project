import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLAlchemy Database URL (SQLite for simplicity).
# Default DB path is anchored to backend/app.db so running from workspace root
# or backend folder resolves to the same database file.
# In production the DATABASE_URL env var should be set (e.g. to
# sqlite:////app/data/app.db) so the container's persistent mount is used.
DEFAULT_SQLITE_PATH = (Path(__file__).resolve().parents[2] / "app.db").as_posix()
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

# Ensure target directory exists for sqlite file-based databases.
if DATABASE_URL.startswith("sqlite:///") and DATABASE_URL != "sqlite:///:memory:":
    sqlite_path = DATABASE_URL.replace("sqlite:///", "", 1)
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

# Create engine with SQLite-specific connection args only for SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()
