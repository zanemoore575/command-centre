from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import base64
import PyPDF2
import io

from app.database import get_db
from app.services.agentic_chat_service import AgenticChatService
from app.services.chat_service import ChatService
from app.services.file_storage_service import FileStorageService
from app.models.chat_message import ChatMessage
from app.models.file_attachment import FileAttachment

router = APIRouter(prefix="/api/chat", tags=["chat"])
agentic_service = AgenticChatService()
chat_service = ChatService()  # Keep for backwards compatibility
file_storage = FileStorageService()


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


@router.post("/messages/agentic")
async def send_message_agentic(
    message: str = Form(...),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db)
):
    """
    Send a message with agentic AI processing.
    Supports images, PDFs, and multi-step reasoning with tool use.

    Files are saved permanently and linked to journal entries.

    Returns streaming responses showing thinking process.
    """
    # Process and save uploaded files
    images = []
    pdf_text = None
    file_metadata = []

    if files:
        for file in files:
            # Read file content
            content = await file.read()

            if file.content_type.startswith("image/"):
                # Encode for Claude API
                encoded = base64.b64encode(content).decode('utf-8')
                images.append({
                    "media_type": file.content_type,
                    "data": encoded
                })

                # Save file to disk
                file_path, _ = file_storage.save_file(
                    content,
                    file.filename,
                    file.content_type
                )

                file_metadata.append({
                    "filename": file.filename,
                    "file_type": file.content_type,
                    "file_size": len(content),
                    "file_path": file_path,
                    "extracted_text": None,  # Will be filled by AI analysis
                    "description": None
                })

            elif file.content_type == "application/pdf":
                # Extract text from PDF
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                pdf_text = "\n\n".join(text_parts)

                # Save PDF file
                file_path, _ = file_storage.save_file(
                    content,
                    file.filename,
                    file.content_type
                )

                file_metadata.append({
                    "filename": file.filename,
                    "file_type": file.content_type,
                    "file_size": len(content),
                    "file_path": file_path,
                    "extracted_text": pdf_text,
                    "description": None
                })

    # Create streaming generator
    async def generate():
        for update in agentic_service.process_message_agentic(
            db,
            message,
            images=images if images else None,
            pdf_text=pdf_text,
            file_metadata=file_metadata if file_metadata else None
        ):
            # Send as Server-Sent Events
            yield f"data: {json.dumps(update)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx/proxies
        }
    )


@router.post("/messages", response_model=ChatResponse)
def send_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to the AI assistant (non-streaming, backwards compatible).

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
    db.query(ChatMessage).delete()
    db.commit()
    return {"message": "Chat history cleared"}
