from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Commitment(Base):
    """Commitment model - action items and promises"""

    __tablename__ = "commitments"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True)

    description = Column(Text, nullable=False)
    due_date = Column(Date, nullable=True, index=True)
    status = Column(String(50), default="open", index=True)  # open, completed, cancelled
    priority = Column(String(50), default="medium")  # low, medium, high

    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="commitments")
    person = relationship("Person", back_populates="commitments")
