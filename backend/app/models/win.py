from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Win(Base):
    """Wins, successes, and positive progress"""
    __tablename__ = "wins"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)

    description = Column(Text, nullable=False)  # The win/success
    category = Column(String(100), nullable=True)  # business, personal, technical, relationship, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="wins")
