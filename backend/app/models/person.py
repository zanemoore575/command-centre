from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Person(Base):
    """Person model - tracks people mentioned in journal entries"""

    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    company = Column(String(255), nullable=True)
    role = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    # Tracking
    first_mentioned_at = Column(DateTime(timezone=True))
    last_mentioned_at = Column(DateTime(timezone=True))
    mention_count = Column(Integer, default=0)

    # Relationship context
    relationship_status = Column(String(50), nullable=True)  # prospect, client, mentor, partner
    notes = Column(String, nullable=True)  # Manual notes

    # Flexible storage
    extra_data = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Relationships
    commitments = relationship("Commitment", back_populates="person")
    pain_points = relationship("PainPoint", back_populates="person")
