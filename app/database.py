"""
Database configuration.

This module creates:

- SQLAlchemy Engine
- Session Factory
- Base ORM class
- Database dependency for FastAPI
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.config import settings


# SQLAlchemy engine.
# Created once and reused across the application.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)


# Session factory.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """
    Provide a database session for a single request.

    FastAPI automatically closes the session
    after the request finishes.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()