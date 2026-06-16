from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import date, datetime
import math

from app.models.journal_entry import JournalEntry
from app.schemas.journal import JournalEntryCreate, JournalEntryUpdate


class JournalService:
    """Service for journal entry operations"""

    @staticmethod
    def create_entry(db: Session, entry_data: JournalEntryCreate) -> JournalEntry:
        """Create a new journal entry"""
        db_entry = JournalEntry(
            content=entry_data.content,
            entry_date=entry_data.entry_date,
            entry_type=entry_data.entry_type,
            mood=entry_data.mood,
            energy_level=entry_data.energy_level,
            is_processed=False
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        return db_entry

    @staticmethod
    def get_entry(db: Session, entry_id: int) -> Optional[JournalEntry]:
        """Get a single journal entry by ID"""
        return db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()

    @staticmethod
    def list_entries(
        db: Session,
        skip: int = 0,
        limit: int = 20,
        entry_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        is_processed: Optional[bool] = None
    ) -> tuple[List[JournalEntry], int]:
        """
        List journal entries with pagination and filters
        Returns: (entries, total_count)
        """
        query = db.query(JournalEntry)

        # Apply filters
        if entry_type:
            query = query.filter(JournalEntry.entry_type == entry_type)
        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)
        if is_processed is not None:
            query = query.filter(JournalEntry.is_processed == is_processed)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        entries = query.order_by(desc(JournalEntry.entry_date)).offset(skip).limit(limit).all()

        return entries, total

    @staticmethod
    def update_entry(
        db: Session,
        entry_id: int,
        entry_data: JournalEntryUpdate
    ) -> Optional[JournalEntry]:
        """Update a journal entry"""
        db_entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        if not db_entry:
            return None

        # Update only provided fields
        update_data = entry_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_entry, field, value)

        # Mark as unprocessed if content changed
        if "content" in update_data:
            db_entry.is_processed = False

        db_entry.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_entry)
        return db_entry

    @staticmethod
    def delete_entry(db: Session, entry_id: int) -> bool:
        """Delete a journal entry"""
        db_entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        if not db_entry:
            return False

        db.delete(db_entry)
        db.commit()
        return True

    @staticmethod
    def get_recent_entries(db: Session, limit: int = 10) -> List[JournalEntry]:
        """Get most recent journal entries"""
        return (
            db.query(JournalEntry)
            .order_by(desc(JournalEntry.entry_date))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_entry_count(db: Session) -> int:
        """Get total number of journal entries"""
        return db.query(func.count(JournalEntry.id)).scalar()

    @staticmethod
    def search_entries(db: Session, search_term: str, limit: int = 20) -> List[JournalEntry]:
        """Search journal entries by content"""
        return (
            db.query(JournalEntry)
            .filter(JournalEntry.content.ilike(f"%{search_term}%"))
            .order_by(desc(JournalEntry.entry_date))
            .limit(limit)
            .all()
        )
