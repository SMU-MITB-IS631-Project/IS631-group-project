from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLAlchemy Database URL (SQLite for simplicity)
DATABASE_URL = "sqlite:///../app.db"

# Create engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Base class for ORM models
Base = declarative_base()

# Session configuration
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Metadata for custom queries
metadata = MetaData()