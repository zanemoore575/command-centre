from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class JournalEntry(Base):
    """Journal entry model - stores raw journal content"""

    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    entry_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Optional metadata
    entry_type = Column(String(50), default="reflection")
    mood = Column(String(50), nullable=True)
    energy_level = Column(Integer, nullable=True)  # 1-5 scale

    # Processing status
    is_processed = Column(Boolean, default=False, index=True)

    # Flexible storage for future fields
    extra_data = Column(JSON, nullable=True)

    # Relationships
    commitments = relationship("Commitment", back_populates="journal_entry", cascade="all, delete-orphan")
    pain_points = relationship("PainPoint", back_populates="journal_entry", cascade="all, delete-orphan")
    entity_mentions = relationship("EntityMention", back_populates="journal_entry", cascade="all, delete-orphan")
    topics = relationship("Topic", back_populates="journal_entry", cascade="all, delete-orphan")
    insights = relationship("Insight", back_populates="journal_entry", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="journal_entry", cascade="all, delete-orphan")
    challenges = relationship("Challenge", back_populates="journal_entry", cascade="all, delete-orphan")
    wins = relationship("Win", back_populates="journal_entry", cascade="all, delete-orphan")
    file_attachments = relationship("FileAttachment", back_populates="journal_entry", cascade="all, delete-orphan")
