from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class EntityMention(Base):
    """Entity mention model - tracks all entity mentions for timeline/context"""

    __tablename__ = "entity_mentions"

    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)

    entity_type = Column(String(50), nullable=False, index=True)  # person, commitment, pain_point, company, etc.
    entity_id = Column(Integer, nullable=True, index=True)  # References the specific entity

    context_snippet = Column(Text, nullable=True)  # Surrounding text for context
    sentiment = Column(String(50), nullable=True)  # positive, negative, neutral

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="entity_mentions")
