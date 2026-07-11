from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Dict, Any, List
from anthropic import Anthropic

from app.models.chat_message import ChatMessage
from app.models.journal_entry import JournalEntry
from app.models.person import Person
from app.models.commitment import Commitment
from app.models.topic import Topic
from app.models.insight import Insight
from app.models.event import Event
from app.models.challenge import Challenge
from app.models.win import Win
from app.services.entity_extraction_service import EntityExtractionService
from app.config import get_settings

settings = get_settings()


class ChatService:
    """Service for handling conversational queries and brain dump extraction"""

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"
        self.extraction_service = EntityExtractionService()

    def process_message(self, db: Session, user_message: str) -> Dict[str, Any]:
        """
        Process a user message - either query the database or extract entities.

        Returns:
            Dict with assistant response, message type, and any extracted data
        """
        # Save user message
        user_msg = ChatMessage(
            role="user",
            content=user_message,
            message_type="pending"
        )
        db.add(user_msg)
        db.commit()

        # Detect intent and gather context
        intent = self._detect_intent(user_message)

        if intent == "query":
            # User is asking a question - search the database
            response = self._handle_query(db, user_message)
            message_type = "query"
            extracted = False
            journal_created = False
        else:
            # User is brain dumping - extract entities
            response = self._handle_brain_dump(db, user_message)
            message_type = "brain_dump"
            extracted = response.get("extracted", False)
            journal_created = response.get("journal_created", False)
            response = response.get("message", "")

        # Update user message with detected type
        user_msg.message_type = message_type
        user_msg.extracted_entities = extracted
        user_msg.journal_entry_created = journal_created
        db.commit()

        # Save assistant response
        assistant_msg = ChatMessage(
            role="assistant",
            content=response,
            message_type=message_type
        )
        db.add(assistant_msg)
        db.commit()

        return {
            "response": response,
            "message_type": message_type,
            "extracted_entities": extracted,
            "journal_created": journal_created
        }

    def _detect_intent(self, message: str) -> str:
        """
        Detect whether this is a query or a brain dump.

        Queries typically:
        - Start with question words (what, who, when, where, how)
        - Ask about past information ("show me", "find", "search")

        Brain dumps typically:
        - Describe what happened ("had a call with", "just finished", "talked to")
        - Express thoughts/feelings ("I think", "feeling", "realized")
        - Mention future actions ("need to", "going to", "planning")
        """
        message_lower = message.lower()

        # Question indicators
        question_starts = ["what", "who", "when", "where", "how", "why", "which", "did i", "have i", "show me", "tell me", "find", "search"]
        if any(message_lower.startswith(q) for q in question_starts):
            return "query"

        if "?" in message:
            return "query"

        # Brain dump indicators
        brain_dump_patterns = [
            "had a", "just had", "talked to", "spoke with", "met with",
            "i think", "i feel", "feeling", "realized", "noticed",
            "need to", "going to", "planning", "tomorrow", "next week",
            "built", "working on", "finished", "completed"
        ]
        if any(pattern in message_lower for pattern in brain_dump_patterns):
            return "brain_dump"

        # Default to brain dump if unclear (captures casual journaling)
        return "brain_dump"

    def _handle_query(self, db: Session, query: str) -> str:
        """Handle a query by searching the database and generating a response"""

        # Get recent chat history for context
        recent_messages = db.query(ChatMessage)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(10)\
            .all()
        recent_messages.reverse()  # Chronological order

        # Build context from database
        context = self._build_context_for_query(db, query)

        # Build conversation history
        conversation = []
        for msg in recent_messages[-6:]:  # Last 3 exchanges
            conversation.append({
                "role": msg.role,
                "content": msg.content
            })

        # Add system context and current query
        system_prompt = f"""You are Command Centre, Zane's personal AI assistant with access to his complete business journey.

You have access to structured data from Zane's journal:

{context}

Answer Zane's questions using ONLY the information above. Be conversational and helpful.

Important:
- Cite specific sources when possible ("In your entry from Jan 15..." or "Sarah mentioned...")
- If you don't have the information, say so clearly
- Be concise but thorough
- Use Zane's own words and context from his journals
"""

        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=conversation + [{"role": "user", "content": query}]
        )

        return response.content[0].text

    def _build_context_for_query(self, db: Session, query: str) -> str:
        """Build relevant context from the database for a query"""

        context_parts = []

        # Get recent journal entries
        recent_entries = db.query(JournalEntry)\
            .order_by(JournalEntry.entry_date.desc())\
            .limit(10)\
            .all()

        if recent_entries:
            context_parts.append("RECENT JOURNAL ENTRIES:")
            for entry in recent_entries:
                context_parts.append(f"- {entry.entry_date}: {entry.content[:200]}...")

        # Get all people
        people = db.query(Person).all()
        if people:
            context_parts.append("\nPEOPLE MENTIONED:")
            for person in people:
                context_parts.append(
                    f"- {person.name}" +
                    (f" ({person.company})" if person.company else "") +
                    (f" - {person.role}" if person.role else "") +
                    f" - mentioned {person.mention_count}x, last: {person.last_mentioned_at.date()}"
                )

        # Get open tasks
        open_tasks = db.query(Commitment).filter(Commitment.status == "open").all()
        if open_tasks:
            context_parts.append("\nOPEN TASKS:")
            for task in open_tasks:
                context_parts.append(f"- {task.description} (priority: {task.priority})")

        # Get topics
        topics = db.query(Topic).order_by(Topic.created_at.desc()).limit(10).all()
        if topics:
            context_parts.append("\nRECENT TOPICS:")
            for topic in topics:
                context_parts.append(f"- {topic.name}: {topic.description or 'N/A'}")

        # Get insights
        insights = db.query(Insight).order_by(Insight.created_at.desc()).limit(10).all()
        if insights:
            context_parts.append("\nRECENT INSIGHTS:")
            for insight in insights:
                context_parts.append(f"- {insight.description}")

        # Get challenges
        challenges = db.query(Challenge).order_by(Challenge.created_at.desc()).limit(10).all()
        if challenges:
            context_parts.append("\nCURRENT CHALLENGES:")
            for challenge in challenges:
                context_parts.append(f"- {challenge.description} (severity: {challenge.severity})")

        # Get wins
        wins = db.query(Win).order_by(Win.created_at.desc()).limit(10).all()
        if wins:
            context_parts.append("\nRECENT WINS:")
            for win in wins:
                context_parts.append(f"- {win.description}")

        return "\n".join(context_parts)

    def _handle_brain_dump(self, db: Session, message: str) -> Dict[str, Any]:
        """Handle a brain dump message by extracting entities"""

        # Create a journal entry from the chat message
        journal_entry = JournalEntry(
            content=message,
            entry_date=date.today(),
            entry_type="chat",
            is_processed=False
        )
        db.add(journal_entry)
        db.commit()
        db.refresh(journal_entry)

        # Extract entities
        extraction_result = self.extraction_service.extract_and_save(db, journal_entry)

        # Generate friendly response
        response_parts = ["Got it! I've captured that information."]

        if extraction_result.get("people_count", 0) > 0:
            people = extraction_result.get("people", [])
            response_parts.append(f"\n👥 People: {', '.join(people)}")

        if extraction_result.get("tasks_count", 0) > 0:
            response_parts.append(f"\n✅ Added {extraction_result['tasks_count']} task(s)")

        if extraction_result.get("topics_count", 0) > 0:
            topics = extraction_result.get("topics", [])
            response_parts.append(f"\n📁 Topics: {', '.join(topics)}")

        if extraction_result.get("insights_count", 0) > 0:
            response_parts.append(f"\n💡 Captured {extraction_result['insights_count']} insight(s)")

        if extraction_result.get("wins_count", 0) > 0:
            response_parts.append(f"\n🎉 Logged {extraction_result['wins_count']} win(s)")

        if extraction_result.get("challenges_count", 0) > 0:
            response_parts.append(f"\n⚠️ Noted {extraction_result['challenges_count']} challenge(s)")

        return {
            "message": " ".join(response_parts),
            "extracted": True,
            "journal_created": True,
            "extraction_result": extraction_result
        }

    def get_chat_history(self, db: Session, limit: int = 50) -> List[ChatMessage]:
        """Get recent chat history"""
        return db.query(ChatMessage)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit)\
            .all()
