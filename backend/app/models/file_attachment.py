from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class FileAttachment(Base):
    """File attachments (PDFs, images, etc.) linked to journal entries"""
    __tablename__ = "file_attachments"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)

    # File metadata
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)  # image/jpeg, application/pdf, etc.
    file_size = Column(BigInteger, nullable=False)  # bytes
    file_path = Column(String(500), nullable=False)  # relative path to stored file

    # Extracted content (for search)
    extracted_text = Column(Text, nullable=True)  # Full text from PDF or OCR
    description = Column(Text, nullable=True)  # AI-generated description for images

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="file_attachments")
