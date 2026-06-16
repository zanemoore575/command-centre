#!/usr/bin/env python3
"""
Migration script to add new entity tables for comprehensive journaling.
This will preserve existing data and add the new tables.
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models.journal_entry import JournalEntry
from app.models.person import Person
from app.models.commitment import Commitment
from app.models.pain_point import PainPoint
from app.models.entity_mention import EntityMention
# Import new models
from app.models.topic import Topic
from app.models.insight import Insight
from app.models.event import Event
from app.models.challenge import Challenge
from app.models.win import Win

print("=" * 60)
print("Migrating Database to Comprehensive Journaling Schema")
print("=" * 60)

# Create new tables (won't affect existing ones)
print("\nCreating new tables...")
Base.metadata.create_all(bind=engine)

print("✓ New tables created successfully!")
print("\nNew entity types now available:")
print("  - Topics/Projects")
print("  - Insights")
print("  - Events/Activities")
print("  - Challenges")
print("  - Wins")

print("\n" + "=" * 60)
print("Migration complete!")
print("=" * 60)
print("\nYour existing data has been preserved.")
print("New entries will now extract comprehensive information.")
print("\nRestart your backend to pick up the changes.")
