import json
from anthropic import Anthropic
from typing import Dict, Any, List
from app.config import get_settings

settings = get_settings()

# Extraction prompt template - Comprehensive brain dump extraction
EXTRACTION_PROMPT = """You are analyzing a personal journal entry. This is a brain dump where the user captures everything from their day - conversations, work, thoughts, tasks, etc.

Your job is to extract and organize ALL the information into structured categories. Be comprehensive and flexible - if something is mentioned, extract it.

Journal Entry:
{entry_content}

Extract the following in JSON format:

1. **People mentioned** - Anyone referenced:
   - name: Full name
   - company: Company/organization if mentioned
   - role: Their role/title/relationship
   - context: Why they were mentioned (1-2 sentences)

2. **Tasks/Actions** - Anything that needs to be done or is being worked on:
   - description: What needs to be done
   - person: Who it's related to (if applicable)
   - deadline: Any mentioned timeline
   - priority: "low", "medium", or "high"

3. **Topics/Projects** - What's being worked on, discussed, or thought about:
   - name: Name of the topic/project
   - description: What it's about
   - category: business, personal, technical, creative, etc.

4. **Insights** - Important realizations, patterns, ideas, learnings:
   - description: The insight or realization
   - category: business, personal, technical, market, customer, etc.

5. **Events/Activities** - What actually happened:
   - description: What happened
   - event_type: meeting, call, work_session, social, etc.

6. **Challenges** - Real problems being experienced (NOT goals or motivations):
   - description: The actual problem/blocker
   - challenge_type: technical, business, personal, customer, etc.
   - severity: "low", "medium", or "high"

7. **Wins** - Successes, progress, positive developments:
   - description: The win or success
   - category: business, personal, technical, relationship, etc.

8. **Overall sentiment**: "positive", "negative", "neutral", or "mixed"

IMPORTANT NOTES:
- Be comprehensive - extract everything mentioned
- Distinguish between goals/motivations (topics) vs actual problems (challenges)
- If someone mentions building something to solve X, X is a topic/insight, NOT a challenge
- If someone is actually struggling with X now, that's a challenge
- Return ONLY valid JSON, no additional text

Return in this exact structure:
{{
  "people": [{{ "name": "str", "company": "str|null", "role": "str|null", "context": "str" }}],
  "tasks": [{{ "description": "str", "person": "str|null", "deadline": "str|null", "priority": "low/medium/high" }}],
  "topics": [{{ "name": "str", "description": "str", "category": "str" }}],
  "insights": [{{ "description": "str", "category": "str" }}],
  "events": [{{ "description": "str", "event_type": "str" }}],
  "challenges": [{{ "description": "str", "challenge_type": "str", "severity": "low/medium/high" }}],
  "wins": [{{ "description": "str", "category": "str" }}],
  "sentiment": "positive/negative/neutral/mixed"
}}

If no items found for a category, return empty array. Be thorough and comprehensive!
"""


class ClaudeClient:
    """Client for interacting with Claude API"""

    def __init__(self):
        # Initialize Anthropic client with just the API key
        try:
            self.client = Anthropic(api_key=settings.anthropic_api_key)
        except Exception as e:
            print(f"Error initializing Anthropic client: {e}")
            raise
        self.model = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5 - best balance of intelligence, speed, and cost

    def extract_entities(self, entry_content: str) -> Dict[str, Any]:
        """
        Extract entities from journal entry using Claude API.

        Returns:
            Dict with keys: people, commitments, pain_points, sentiment
        """
        try:
            prompt = EXTRACTION_PROMPT.format(entry_content=entry_content)

            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract the text response
            response_text = message.content[0].text

            # Strip markdown code blocks if present (```json ... ```)
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            elif response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove closing ```
            response_text = response_text.strip()

            # Parse JSON response
            entities = json.loads(response_text)

            # Validate structure - ensure all required keys exist
            required_keys = ["people", "tasks", "topics", "insights", "events", "challenges", "wins", "sentiment"]
            for key in required_keys:
                if key not in entities:
                    entities[key] = [] if key != "sentiment" else "neutral"

            return entities

        except json.JSONDecodeError as e:
            print(f"Failed to parse Claude response as JSON: {e}")
            print(f"Response was: {response_text}")
            # Return empty structure on parse error
            return {
                "people": [],
                "tasks": [],
                "topics": [],
                "insights": [],
                "events": [],
                "challenges": [],
                "wins": [],
                "sentiment": "neutral"
            }
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            # Return empty structure on API error
            return {
                "people": [],
                "tasks": [],
                "topics": [],
                "insights": [],
                "events": [],
                "challenges": [],
                "wins": [],
                "sentiment": "neutral"
            }

    def analyze_patterns(self, entries: List[str]) -> Dict[str, Any]:
        """
        Analyze patterns across multiple journal entries.
        (Future feature for weekly insights)
        """
        # Placeholder for Phase 5
        pass
