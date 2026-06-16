from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class PainPoint(Base):
    """Pain point model - customer problems identified"""

    __tablename__ = "pain_points"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), nullable=True)

    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=True, index=True)  # quotes, scheduling, communication, etc.
    severity = Column(String(50), default="medium")  # low, medium, high

    frequency_mentioned = Column(Integer, default=1)
    first_mentioned_at = Column(DateTime(timezone=True), server_default=func.now())
    last_mentioned_at = Column(DateTime(timezone=True), server_default=func.now())

    validation_status = Column(String(50), default="testing")  # testing, validated, invalidated

    extra_data = Column(JSON, nullable=True)

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="pain_points")
    person = relationship("Person", back_populates="pain_points")
