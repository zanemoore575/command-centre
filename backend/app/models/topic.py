from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Topic(Base):
    """Topics/Projects being worked on or discussed"""
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(200), nullable=False)  # Topic/project name
    description = Column(Text, nullable=True)  # What it's about
    category = Column(String(100), nullable=True)  # business, personal, technical, creative, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="topics")
