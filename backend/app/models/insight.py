from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Insight(Base):
    """Key insights, realizations, and ideas"""
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)

    description = Column(Text, nullable=False)  # The insight/realization
    category = Column(String(100), nullable=True)  # business, personal, technical, market, customer, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="insights")
