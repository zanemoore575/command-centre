from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Challenge(Base):
    """Challenges, problems, and blockers"""
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)

    description = Column(Text, nullable=False)  # The challenge/problem
    challenge_type = Column(String(100), nullable=True)  # technical, business, personal, customer, etc.
    severity = Column(String(50), default="medium")  # low, medium, high

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="challenges")
