from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

try:
    from backend.core.database import Base
except ModuleNotFoundError:
    from core.database import Base


class Page(Base):
    """
    Stores extracted text for each page of a book PDF.
    """

    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    pdf_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    book = relationship("Book", back_populates="pages")
