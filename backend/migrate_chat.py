#!/usr/bin/env python3
"""
Migration script to add chat_messages table
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models.chat_message import ChatMessage

print("=" * 60)
print("Adding Chat Messages Table")
print("=" * 60)

print("\nCreating chat_messages table...")
Base.metadata.create_all(bind=engine)

print("✓ Chat messages table created successfully!")
print("\n" + "=" * 60)
print("Migration complete!")
print("=" * 60)
