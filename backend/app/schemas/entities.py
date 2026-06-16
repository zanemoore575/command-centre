from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class PersonResponse(BaseModel):
    """Schema for person response"""
    id: int
    name: str
    company: Optional[str] = None
    role: Optional[str] = None
    mention_count: int
    first_mentioned_at: Optional[datetime] = None
    last_mentioned_at: Optional[datetime] = None
    relationship_status: Optional[str] = None

    class Config:
        from_attributes = True


class CommitmentResponse(BaseModel):
    """Schema for commitment response"""
    id: int
    description: str
    status: str
    priority: str
    person_id: Optional[int] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PainPointResponse(BaseModel):
    """Schema for pain point response"""
    id: int
    description: str
    category: Optional[str] = None
    severity: str
    frequency_mentioned: int
    validation_status: str
    person_id: Optional[int] = None

    class Config:
        from_attributes = True
