from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from app.database import Base


class ChatMessage(Base):
    """Chat message model - stores conversation history with the AI assistant"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)

    # Message content
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # Message metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Intent detection
    message_type = Column(String(50), nullable=True)  # 'query', 'brain_dump', 'casual', etc.

    # If this message resulted in entity extraction
    extracted_entities = Column(Boolean, default=False)
    journal_entry_created = Column(Boolean, default=False)

    # Store any metadata (sources used for queries, entities extracted, etc.)
    extra_data = Column(JSON, nullable=True)
