import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLAlchemy Database URL (SQLite for simplicity)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../app.db")

# Create engine with SQLite-specific connection args only for SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()
