import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()

# Use absolute path override via env if needed; fallback keeps local setup simple.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./booktures2.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    # Import models here so SQLAlchemy registers metadata before create_all().
    try:
        from backend.models.book import Book  # noqa: F401
        from backend.models.page import Page  # noqa: F401
    except ModuleNotFoundError:
        from models.book import Book  # noqa: F401
        from models.page import Page  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    # FastAPI dependency that provides/cleans a DB session per request.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
