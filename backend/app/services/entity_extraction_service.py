from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any

from app.models.journal_entry import JournalEntry
from app.models.person import Person
from app.models.commitment import Commitment
from app.models.pain_point import PainPoint
from app.models.entity_mention import EntityMention
from app.models.topic import Topic
from app.models.insight import Insight
from app.models.event import Event
from app.models.challenge import Challenge
from app.models.win import Win
from app.utils.claude_client import ClaudeClient


class EntityExtractionService:
    """Service for extracting entities from journal entries using AI"""

    def __init__(self):
        self.claude = ClaudeClient()

    def extract_and_save(self, db: Session, journal_entry: JournalEntry) -> Dict[str, Any]:
        """
        Extract entities from journal entry and save to database.

        Returns:
            Dict with extraction results and counts
        """
        # Call Claude API to extract entities
        extracted = self.claude.extract_entities(journal_entry.content)

        # Process and save all entity types
        people_created = self._process_people(db, journal_entry, extracted.get("people", []))
        tasks_created = self._process_tasks(db, journal_entry, extracted.get("tasks", []), people_created)
        topics_created = self._process_topics(db, journal_entry, extracted.get("topics", []))
        insights_created = self._process_insights(db, journal_entry, extracted.get("insights", []))
        events_created = self._process_events(db, journal_entry, extracted.get("events", []))
        challenges_created = self._process_challenges(db, journal_entry, extracted.get("challenges", []))
        wins_created = self._process_wins(db, journal_entry, extracted.get("wins", []))

        # Mark journal entry as processed
        journal_entry.is_processed = True
        db.commit()

        return {
            "people_count": len(people_created),
            "tasks_count": len(tasks_created),
            "topics_count": len(topics_created),
            "insights_count": len(insights_created),
            "events_count": len(events_created),
            "challenges_count": len(challenges_created),
            "wins_count": len(wins_created),
            "sentiment": extracted.get("sentiment", "neutral"),
            "people": [p.name for p in people_created],
            "tasks": [t.description for t in tasks_created],
            "topics": [t.name for t in topics_created],
            "insights": [i.description[:50] for i in insights_created],
            "events": [e.description[:50] for e in events_created],
            "challenges": [c.description[:50] for c in challenges_created],
            "wins": [w.description[:50] for w in wins_created]
        }

    def _process_people(
        self, db: Session, journal_entry: JournalEntry, people_data: list
    ) -> list[Person]:
        """Process and save people entities"""
        people_created = []

        for person_data in people_data:
            name = person_data.get("name")
            if not name:
                continue

            # Check if person already exists
            person = db.query(Person).filter(Person.name == name).first()

            if person:
                # Update existing person
                person.mention_count += 1
                person.last_mentioned_at = datetime.utcnow()

                # Update company/role if provided and not already set
                if person_data.get("company") and not person.company:
                    person.company = person_data.get("company")
                if person_data.get("role") and not person.role:
                    person.role = person_data.get("role")
            else:
                # Create new person
                person = Person(
                    name=name,
                    company=person_data.get("company"),
                    role=person_data.get("role"),
                    first_mentioned_at=datetime.utcnow(),
                    last_mentioned_at=datetime.utcnow(),
                    mention_count=1
                )
                db.add(person)
                db.flush()  # Get the ID

            # Create entity mention
            mention = EntityMention(
                journal_entry_id=journal_entry.id,
                entity_type="person",
                entity_id=person.id,
                context_snippet=person_data.get("context", "")[:200],
                sentiment="neutral"
            )
            db.add(mention)

            people_created.append(person)

        db.commit()
        return people_created

    def _process_tasks(
        self,
        db: Session,
        journal_entry: JournalEntry,
        tasks_data: list,
        people_created: list[Person]
    ) -> list[Commitment]:
        """Process and save task/commitment entities"""
        tasks_created = []

        for task_data in tasks_data:
            description = task_data.get("description")
            if not description:
                continue

            # Find associated person if mentioned
            person_id = None
            person_name = task_data.get("person")
            if person_name:
                person = db.query(Person).filter(Person.name == person_name).first()
                if person:
                    person_id = person.id

            # Create task/commitment
            task = Commitment(
                journal_entry_id=journal_entry.id,
                person_id=person_id,
                description=description,
                status="open",
                priority=task_data.get("priority", "medium")
            )

            db.add(task)
            db.flush()

            # Create entity mention
            mention = EntityMention(
                journal_entry_id=journal_entry.id,
                entity_type="commitment",
                entity_id=task.id,
                context_snippet=description[:200]
            )
            db.add(mention)

            tasks_created.append(task)

        db.commit()
        return tasks_created

    def _process_topics(
        self, db: Session, journal_entry: JournalEntry, topics_data: list
    ) -> list[Topic]:
        """Process and save topic entities"""
        topics_created = []

        for topic_data in topics_data:
            name = topic_data.get("name")
            if not name:
                continue

            topic = Topic(
                journal_entry_id=journal_entry.id,
                name=name,
                description=topic_data.get("description"),
                category=topic_data.get("category", "general")
            )

            db.add(topic)
            topics_created.append(topic)

        db.commit()
        return topics_created

    def _process_insights(
        self, db: Session, journal_entry: JournalEntry, insights_data: list
    ) -> list[Insight]:
        """Process and save insight entities"""
        insights_created = []

        for insight_data in insights_data:
            description = insight_data.get("description")
            if not description:
                continue

            insight = Insight(
                journal_entry_id=journal_entry.id,
                description=description,
                category=insight_data.get("category", "general")
            )

            db.add(insight)
            insights_created.append(insight)

        db.commit()
        return insights_created

    def _process_events(
        self, db: Session, journal_entry: JournalEntry, events_data: list
    ) -> list[Event]:
        """Process and save event entities"""
        events_created = []

        for event_data in events_data:
            description = event_data.get("description")
            if not description:
                continue

            event = Event(
                journal_entry_id=journal_entry.id,
                description=description,
                event_type=event_data.get("event_type", "general")
            )

            db.add(event)
            events_created.append(event)

        db.commit()
        return events_created

    def _process_challenges(
        self, db: Session, journal_entry: JournalEntry, challenges_data: list
    ) -> list[Challenge]:
        """Process and save challenge entities"""
        challenges_created = []

        for challenge_data in challenges_data:
            description = challenge_data.get("description")
            if not description:
                continue

            challenge = Challenge(
                journal_entry_id=journal_entry.id,
                description=description,
                challenge_type=challenge_data.get("challenge_type", "general"),
                severity=challenge_data.get("severity", "medium")
            )

            db.add(challenge)
            challenges_created.append(challenge)

        db.commit()
        return challenges_created

    def _process_wins(
        self, db: Session, journal_entry: JournalEntry, wins_data: list
    ) -> list[Win]:
        """Process and save win entities"""
        wins_created = []

        for win_data in wins_data:
            description = win_data.get("description")
            if not description:
                continue

            win = Win(
                journal_entry_id=journal_entry.id,
                description=description,
                category=win_data.get("category", "general")
            )

            db.add(win)
            wins_created.append(win)

        db.commit()
        return wins_created
