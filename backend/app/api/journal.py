from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
import math

from app.database import get_db
from app.services.journal_service import JournalService
from app.services.entity_extraction_service import EntityExtractionService
from app.schemas.journal import (
    JournalEntryCreate,
    JournalEntryUpdate,
    JournalEntryResponse,
    JournalEntryList
)

router = APIRouter()
extraction_service = EntityExtractionService()


@router.post("/entries", response_model=JournalEntryResponse, status_code=201)
def create_journal_entry(
    entry: JournalEntryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new journal entry and trigger AI extraction"""
    db_entry = JournalService.create_entry(db, entry)

    # Trigger entity extraction in background
    background_tasks.add_task(extraction_service.extract_and_save, db, db_entry)

    return db_entry


@router.get("/entries", response_model=JournalEntryList)
def list_journal_entries(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    entry_type: Optional[str] = Query(None, description="Filter by entry type"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    is_processed: Optional[bool] = Query(None, description="Filter by processing status"),
    db: Session = Depends(get_db)
):
    """List journal entries with pagination and filters"""
    skip = (page - 1) * page_size
    entries, total = JournalService.list_entries(
        db,
        skip=skip,
        limit=page_size,
        entry_type=entry_type,
        start_date=start_date,
        end_date=end_date,
        is_processed=is_processed
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/entries/{entry_id}", response_model=JournalEntryResponse)
def get_journal_entry(
    entry_id: int,
    db: Session = Depends(get_db)
):
    """Get a single journal entry by ID"""
    entry = JournalService.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.put("/entries/{entry_id}", response_model=JournalEntryResponse)
def update_journal_entry(
    entry_id: int,
    entry_update: JournalEntryUpdate,
    db: Session = Depends(get_db)
):
    """Update a journal entry"""
    entry = JournalService.update_entry(db, entry_id, entry_update)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
def delete_journal_entry(
    entry_id: int,
    db: Session = Depends(get_db)
):
    """Delete a journal entry"""
    success = JournalService.delete_entry(db, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return None


@router.get("/entries/recent/{limit}", response_model=list[JournalEntryResponse])
def get_recent_entries(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get most recent journal entries"""
    entries = JournalService.get_recent_entries(db, limit)
    return entries


@router.get("/search", response_model=list[JournalEntryResponse])
def search_entries(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search journal entries by content"""
    entries = JournalService.search_entries(db, q, limit)
    return entries


@router.post("/entries/{entry_id}/extract")
def extract_entities_manually(
    entry_id: int,
    db: Session = Depends(get_db)
):
    """Manually trigger entity extraction for a journal entry"""
    entry = JournalService.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    # Run extraction
    result = extraction_service.extract_and_save(db, entry)

    return {
        "message": "Extraction completed",
        "entry_id": entry_id,
        "results": result
    }


@router.get("/entries/{entry_id}/entities")
def get_entry_entities(
    entry_id: int,
    db: Session = Depends(get_db)
):
    """Get extracted entities for a journal entry"""
    from app.models.person import Person

    entry = JournalService.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    # Get unique people mentioned in this entry
    people_ids = [
        mention.entity_id
        for mention in entry.entity_mentions
        if mention.entity_type == "person"
    ]
    people = db.query(Person).filter(Person.id.in_(people_ids)).all() if people_ids else []

    return {
        "people": people,
        "tasks": entry.commitments,  # Tasks are stored as commitments
        "topics": entry.topics,
        "insights": entry.insights,
        "events": entry.events,
        "challenges": entry.challenges,
        "wins": entry.wins,
        "pain_points": entry.pain_points,  # Keep for backwards compatibility
        "is_processed": entry.is_processed
    }
