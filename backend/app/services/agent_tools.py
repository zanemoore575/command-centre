"""
Agent tools for querying the CAiS database.
These tools can be called by the AI agent to search and retrieve information.
"""
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from app.models.journal_entry import JournalEntry
from app.models.person import Person
from app.models.commitment import Commitment
from app.models.topic import Topic
from app.models.insight import Insight
from app.models.event import Event
from app.models.challenge import Challenge
from app.models.win import Win
from app.models.chat_message import ChatMessage
from app.models.file_attachment import FileAttachment


class AgentTools:
    """Tools that the AI agent can use to query the database"""

    def __init__(self, db: Session):
        self.db = db

    def search_people(self, name: Optional[str] = None, company: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for people in the database.

        Args:
            name: Person's name (partial match)
            company: Company name (partial match)

        Returns:
            List of people with their details
        """
        query = self.db.query(Person)

        if name:
            query = query.filter(Person.name.ilike(f"%{name}%"))
        if company:
            query = query.filter(Person.company.ilike(f"%{company}%"))

        people = query.all()

        return [{
            "name": p.name,
            "company": p.company,
            "role": p.role,
            "mention_count": p.mention_count,
            "first_mentioned": str(p.first_mentioned_at.date()) if p.first_mentioned_at else None,
            "last_mentioned": str(p.last_mentioned_at.date()) if p.last_mentioned_at else None
        } for p in people]

    def search_journal_entries(
        self,
        query: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search journal entries.

        Args:
            query: Search term (searches in content)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum number of results

        Returns:
            List of matching journal entries
        """
        db_query = self.db.query(JournalEntry)

        if query:
            db_query = db_query.filter(JournalEntry.content.ilike(f"%{query}%"))

        if start_date:
            db_query = db_query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            db_query = db_query.filter(JournalEntry.entry_date <= end_date)

        entries = db_query.order_by(JournalEntry.entry_date.desc()).limit(limit).all()

        return [{
            "id": e.id,
            "date": str(e.entry_date),
            "content": e.content[:300] + "..." if len(e.content) > 300 else e.content,
            "entry_type": e.entry_type,
            "mood": e.mood,
            "is_processed": e.is_processed
        } for e in entries]

    def get_full_journal_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """
        Get complete journal entry with all extracted entities.

        Args:
            entry_id: Journal entry ID

        Returns:
            Full entry with entities or None if not found
        """
        entry = self.db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
        if not entry:
            return None

        return {
            "id": entry.id,
            "date": str(entry.entry_date),
            "content": entry.content,
            "entry_type": entry.entry_type,
            "mood": entry.mood,
            "energy_level": entry.energy_level,
            "topics": [{"name": t.name, "description": t.description} for t in entry.topics],
            "insights": [{"description": i.description, "category": i.category} for i in entry.insights],
            "events": [{"description": e.description, "type": e.event_type} for e in entry.events],
            "challenges": [{"description": c.description, "severity": c.severity} for c in entry.challenges],
            "wins": [{"description": w.description, "category": w.category} for w in entry.wins]
        }

    def get_tasks(
        self,
        status: Optional[str] = None,
        person_name: Optional[str] = None,
        priority: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get tasks/commitments.

        Args:
            status: Task status (open, completed, cancelled)
            person_name: Filter by person name
            priority: Task priority (low, medium, high)

        Returns:
            List of tasks
        """
        query = self.db.query(Commitment)

        if status:
            query = query.filter(Commitment.status == status)
        if priority:
            query = query.filter(Commitment.priority == priority)

        if person_name:
            person = self.db.query(Person).filter(Person.name.ilike(f"%{person_name}%")).first()
            if person:
                query = query.filter(Commitment.person_id == person.id)

        tasks = query.order_by(Commitment.created_at.desc()).all()

        return [{
            "id": t.id,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "person": t.person.name if t.person else None,
            "created_at": str(t.created_at.date())
        } for t in tasks]

    def get_insights(self, category: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get insights.

        Args:
            category: Filter by category
            limit: Maximum results

        Returns:
            List of insights
        """
        query = self.db.query(Insight)

        if category:
            query = query.filter(Insight.category.ilike(f"%{category}%"))

        insights = query.order_by(Insight.created_at.desc()).limit(limit).all()

        return [{
            "description": i.description,
            "category": i.category,
            "date": str(i.created_at.date())
        } for i in insights]

    def get_challenges(self, severity: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get challenges/blockers.

        Args:
            severity: Filter by severity (low, medium, high)
            limit: Maximum results

        Returns:
            List of challenges
        """
        query = self.db.query(Challenge)

        if severity:
            query = query.filter(Challenge.severity == severity)

        challenges = query.order_by(Challenge.created_at.desc()).limit(limit).all()

        return [{
            "description": c.description,
            "severity": c.severity,
            "challenge_type": c.challenge_type,
            "date": str(c.created_at.date())
        } for c in challenges]

    def get_wins(self, category: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get wins/successes.

        Args:
            category: Filter by category
            limit: Maximum results

        Returns:
            List of wins
        """
        query = self.db.query(Win)

        if category:
            query = query.filter(Win.category.ilike(f"%{category}%"))

        wins = query.order_by(Win.created_at.desc()).limit(limit).all()

        return [{
            "description": w.description,
            "category": w.category,
            "date": str(w.created_at.date())
        } for w in wins]

    def get_topics(self, category: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get topics/projects being worked on.

        Args:
            category: Filter by category
            limit: Maximum results

        Returns:
            List of topics
        """
        query = self.db.query(Topic)

        if category:
            query = query.filter(Topic.category.ilike(f"%{category}%"))

        topics = query.order_by(Topic.created_at.desc()).limit(limit).all()

        return [{
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "date": str(t.created_at.date())
        } for t in topics]

    def get_recent_activity(self, days: int = 7) -> Dict[str, Any]:
        """
        Get summary of recent activity.

        Args:
            days: Number of days to look back

        Returns:
            Summary of recent activity
        """
        cutoff_date = date.today() - timedelta(days=days)

        recent_entries = self.db.query(JournalEntry)\
            .filter(JournalEntry.entry_date >= cutoff_date)\
            .count()

        recent_people = self.db.query(Person)\
            .filter(Person.last_mentioned_at >= datetime.now() - timedelta(days=days))\
            .all()

        open_tasks = self.db.query(Commitment)\
            .filter(Commitment.status == "open")\
            .count()

        return {
            "period": f"Last {days} days",
            "journal_entries": recent_entries,
            "people_mentioned": len(recent_people),
            "people_names": [p.name for p in recent_people],
            "open_tasks": open_tasks
        }

    def search_chat_history(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search previous chat conversations.

        Args:
            query: Search term
            limit: Maximum results

        Returns:
            List of matching chat messages with context
        """
        messages = self.db.query(ChatMessage)\
            .filter(ChatMessage.content.ilike(f"%{query}%"))\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit)\
            .all()

        return [{
            "role": m.role,
            "content": m.content[:200] + "..." if len(m.content) > 200 else m.content,
            "message_type": m.message_type,
            "date": str(m.created_at.date())
        } for m in messages]

    def search_documents(
        self,
        query: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search uploaded documents (PDFs, images, etc.).

        Args:
            query: Search term (searches in filename, extracted text, and description)
            file_type: Filter by file type (image, pdf, etc.)
            limit: Maximum results

        Returns:
            List of matching documents with metadata
        """
        db_query = self.db.query(FileAttachment)

        if query:
            # Search in filename, extracted text, and description
            search_filter = (
                FileAttachment.filename.ilike(f"%{query}%") |
                FileAttachment.extracted_text.ilike(f"%{query}%") |
                FileAttachment.description.ilike(f"%{query}%")
            )
            db_query = db_query.filter(search_filter)

        if file_type:
            if file_type.lower() == "image":
                db_query = db_query.filter(FileAttachment.file_type.like("image/%"))
            elif file_type.lower() == "pdf":
                db_query = db_query.filter(FileAttachment.file_type == "application/pdf")
            else:
                db_query = db_query.filter(FileAttachment.file_type.ilike(f"%{file_type}%"))

        documents = db_query.order_by(FileAttachment.created_at.desc()).limit(limit).all()

        return [{
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "file_path": d.file_path,
            "extracted_text": d.extracted_text[:500] + "..." if d.extracted_text and len(d.extracted_text) > 500 else d.extracted_text,
            "description": d.description,
            "uploaded_date": str(d.created_at.date()),
            "journal_entry_id": d.journal_entry_id
        } for d in documents]


# Tool definitions for Claude API
TOOL_DEFINITIONS = [
    {
        "name": "search_people",
        "description": "Search for people mentioned in the journal. Can search by name or company. Returns details about each person including how many times they were mentioned and when.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Person's name (partial match works)"
                },
                "company": {
                    "type": "string",
                    "description": "Company name (partial match works)"
                }
            }
        }
    },
    {
        "name": "search_journal_entries",
        "description": "Search journal entries by content, date range, or both. Returns matching entries with previews.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term to find in journal content"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 10)"
                }
            }
        }
    },
    {
        "name": "get_full_journal_entry",
        "description": "Get the complete content of a specific journal entry including all extracted entities (topics, insights, events, challenges, wins).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_id": {
                    "type": "integer",
                    "description": "The journal entry ID"
                }
            },
            "required": ["entry_id"]
        }
    },
    {
        "name": "get_tasks",
        "description": "Get tasks/action items. Can filter by status (open/completed), person, or priority.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Task status: open, completed, or cancelled"
                },
                "person_name": {
                    "type": "string",
                    "description": "Filter tasks related to a specific person"
                },
                "priority": {
                    "type": "string",
                    "description": "Task priority: low, medium, or high"
                }
            }
        }
    },
    {
        "name": "get_insights",
        "description": "Get insights and realizations from journal entries. Can filter by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (e.g., business, personal, technical)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)"
                }
            }
        }
    },
    {
        "name": "get_challenges",
        "description": "Get current challenges and blockers. Can filter by severity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "Filter by severity: low, medium, or high"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)"
                }
            }
        }
    },
    {
        "name": "get_wins",
        "description": "Get wins and successes. Can filter by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (e.g., business, personal, technical)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)"
                }
            }
        }
    },
    {
        "name": "get_topics",
        "description": "Get topics and projects being worked on. Can filter by category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (e.g., business, personal, technical)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)"
                }
            }
        }
    },
    {
        "name": "get_recent_activity",
        "description": "Get a summary of recent activity including journal entries, people mentioned, and open tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 7)"
                }
            }
        }
    },
    {
        "name": "search_chat_history",
        "description": "Search previous chat conversations for specific topics or questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term to find in chat history"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 10)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_documents",
        "description": "Search uploaded documents (PDFs, images, etc.) by filename, extracted text, or AI description. Use this when the user asks about previously uploaded files or documents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term to find in filename, extracted text, or description"
                },
                "file_type": {
                    "type": "string",
                    "description": "Filter by file type: 'image', 'pdf', or specific MIME type"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 10)"
                }
            }
        }
    }
]
