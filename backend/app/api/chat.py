from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])
chat_service = ChatService()


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message"""
    message: str


class ChatMessageResponse(BaseModel):
    """Response model for chat messages"""
    id: int
    role: str
    content: str
    created_at: datetime
    message_type: Optional[str] = None

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    """Response model for chat API"""
    response: str
    message_type: str
    extracted_entities: bool = False
    journal_created: bool = False


@router.post("/messages", response_model=ChatResponse)
def send_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to the AI assistant.

    The system will automatically detect if this is:
    - A query (asking for information from your journal history)
    - A brain dump (casual journaling that should be extracted)
    """
    result = chat_service.process_message(db, request.message)
    return result


@router.get("/messages", response_model=List[ChatMessageResponse])
def get_chat_history(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get chat conversation history"""
    messages = chat_service.get_chat_history(db, limit)
    messages.reverse()  # Return in chronological order
    return messages


@router.delete("/messages")
def clear_chat_history(db: Session = Depends(get_db)):
    """Clear all chat history"""
    from app.models.chat_message import ChatMessage
    db.query(ChatMessage).delete()
    db.commit()
    return {"message": "Chat history cleared"}
