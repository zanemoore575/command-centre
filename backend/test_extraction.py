#!/usr/bin/env python3
"""
Test the extraction service directly
"""
import sys
sys.path.insert(0, '/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend')

from app.database import SessionLocal
from app.models.journal_entry import JournalEntry
from app.services.entity_extraction_service import EntityExtractionService

# Create a test entry
db = SessionLocal()

print("=" * 60)
print("Testing Entity Extraction Service")
print("=" * 60)

# Find the most recent entry
entry = db.query(JournalEntry).order_by(JournalEntry.created_at.desc()).first()

if not entry:
    print("\nNo journal entries found. Please create one first.")
    exit(1)

print(f"\nFound entry #{entry.id}")
print(f"Created: {entry.created_at}")
print(f"Content preview: {entry.content[:100]}...")
print(f"Is processed: {entry.is_processed}")

print("\n" + "=" * 60)
print("Running extraction...")
print("=" * 60)

extraction_service = EntityExtractionService()

try:
    result = extraction_service.extract_and_save(db, entry)

    print("\n✓ Extraction completed!")
    print("\nResults:")
    print(f"  People: {len(result.get('people', []))}")
    print(f"  Commitments: {len(result.get('commitments', []))}")
    print(f"  Pain Points: {len(result.get('pain_points', []))}")
    print(f"  Sentiment: {result.get('sentiment', 'unknown')}")

    if result.get('people'):
        print("\n  People details:")
        for person in result['people']:
            print(f"    - {person.get('name')} ({person.get('company', 'No company')})")

    if result.get('commitments'):
        print("\n  Commitments:")
        for commitment in result['commitments']:
            print(f"    - {commitment.get('description')[:80]}...")

    if result.get('pain_points'):
        print("\n  Pain Points:")
        for pain_point in result['pain_points']:
            print(f"    - {pain_point.get('description')[:80]}...")

    print("\n" + "=" * 60)
    print("Extraction test successful!")
    print("=" * 60)

except Exception as e:
    print(f"\n✗ Error during extraction: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

finally:
    db.close()
