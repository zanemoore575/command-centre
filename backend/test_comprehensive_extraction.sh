#!/bin/bash

# Test comprehensive brain dump extraction

echo "======================================================================"
echo "Testing Comprehensive Brain Dump Extraction"
echo "======================================================================"
echo ""

# Create a comprehensive test entry
curl -X POST http://localhost:8000/api/journal/entries \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Had an amazing day today! Started with a call with Sarah from BuildTech - she mentioned their team is drowning in quote follow-ups, spending like 15 hours a week on it. Seems like a huge opportunity. I committed to sending her a demo by Thursday.\n\nSpent the afternoon building out the comprehensive extraction feature for CAiS Command Centre. Realized that we need to make the system flexible enough to handle any kind of brain dump, not just business intelligence. This is a key insight - the app should be my AI sidekick that knows everything, not just a pain point tracker.\n\nAlso had coffee with Mike, an old friend who'\''s now doing construction management. He'\''s interested in what we'\''re building. Need to follow up with him next week.\n\nFeeling really good about the direction of the product. The comprehensive extraction approach is definitely the right move. Only challenge is making sure the Claude API prompts are well-tuned to distinguish between goals and actual problems.\n\nTomorrow I need to deploy the app to a server and start testing with real journal entries.",
    "entry_date": "2026-01-15",
    "entry_type": "reflection",
    "mood": "productive",
    "energy_level": 4
  }'

echo ""
echo ""
echo "Entry created! Waiting 5 seconds for AI extraction..."
sleep 5

echo ""
echo "======================================================================"
echo "Fetching Extraction Results"
echo "======================================================================"
echo ""

# Get the latest entry (should be ID 4 or higher)
ENTRY_ID=$(curl -s http://localhost:8000/api/journal/entries | python3 -c "import sys, json; entries = json.load(sys.stdin)['entries']; print(entries[0]['id'] if entries else 'unknown')")

echo "Latest entry ID: $ENTRY_ID"
echo ""

# Fetch entities
curl -s "http://localhost:8000/api/journal/entries/$ENTRY_ID/entities" | python3 -m json.tool

echo ""
echo "======================================================================"
echo "Test Complete!"
echo "======================================================================"
echo ""
echo "Check the output above to verify all entity types are extracted:"
echo "  - People (Sarah, Mike)"
echo "  - Tasks (send demo, follow up with Mike, deploy app)"
echo "  - Topics (CAiS Command Centre, comprehensive extraction)"
echo "  - Insights (system should be flexible, AI sidekick concept)"
echo "  - Events (call with Sarah, coffee with Mike, building feature)"
echo "  - Challenges (tuning Claude prompts)"
echo "  - Wins (feeling good about direction, right approach)"
echo ""
