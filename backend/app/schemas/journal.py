from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class JournalEntryBase(BaseModel):
    """Base schema for journal entries"""
    content: str = Field(..., min_length=1, description="Journal entry content")
    entry_date: date = Field(..., description="Date the event occurred")
    entry_type: Optional[str] = Field("reflection", description="Type of entry")
    mood: Optional[str] = Field(None, description="Mood during entry")
    energy_level: Optional[int] = Field(None, ge=1, le=5, description="Energy level (1-5)")


class JournalEntryCreate(JournalEntryBase):
    """Schema for creating a journal entry"""
    pass


class JournalEntryUpdate(BaseModel):
    """Schema for updating a journal entry"""
    content: Optional[str] = Field(None, min_length=1)
    entry_date: Optional[date] = None
    entry_type: Optional[str] = None
    mood: Optional[str] = None
    energy_level: Optional[int] = Field(None, ge=1, le=5)


class JournalEntryResponse(JournalEntryBase):
    """Schema for journal entry response"""
    id: int
    created_at: datetime
    updated_at: datetime
    is_processed: bool

    class Config:
        from_attributes = True


class JournalEntryWithEntities(JournalEntryResponse):
    """Schema for journal entry with extracted entities"""
    people_mentioned: List[str] = Field(default_factory=list)
    commitments_count: int = 0
    pain_points_count: int = 0

    class Config:
        from_attributes = True


class JournalEntryList(BaseModel):
    """Schema for paginated journal entry list"""
    entries: List[JournalEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
