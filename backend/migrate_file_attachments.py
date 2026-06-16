#!/usr/bin/env python3
"""
Migration script to add file_attachments table and create upload directory
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app.models.file_attachment import FileAttachment

print("=" * 60)
print("Adding File Attachments Support")
print("=" * 60)

# Create uploads directory
uploads_dir = Path(__file__).parent / "uploads"
uploads_dir.mkdir(exist_ok=True)
print(f"\n✓ Created uploads directory: {uploads_dir}")

# Create subdirectories
(uploads_dir / "images").mkdir(exist_ok=True)
(uploads_dir / "documents").mkdir(exist_ok=True)
print("✓ Created subdirectories: images/, documents/")

# Create database table
print("\nCreating file_attachments table...")
Base.metadata.create_all(bind=engine)
print("✓ file_attachments table created successfully!")

print("\n" + "=" * 60)
print("Migration complete!")
print("=" * 60)
print("\nFiles uploaded through chat will now be:")
print("  - Saved to disk (uploads/)")
print("  - Linked to journal entries")
print("  - Extracted and searchable")
print("  - Permanently part of your knowledge base")
