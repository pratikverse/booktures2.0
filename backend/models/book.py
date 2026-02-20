from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

try:
    from backend.core.database import Base
except ModuleNotFoundError:
    from core.database import Base


class Book(Base):
    """
    Book container model.
    Phase 1 stores minimal metadata + relation to extracted pages.
    """

    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    total_pages = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pages = relationship("Page", back_populates="book", cascade="all, delete-orphan")
