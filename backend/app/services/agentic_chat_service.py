"""
Agentic chat service with extended thinking, tool use, and multi-step reasoning.
Simplified approach: Separate API calls for each phase.
"""
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Generator
from anthropic import Anthropic
import json
import base64

from app.models.chat_message import ChatMessage
from app.models.journal_entry import JournalEntry
from app.models.file_attachment import FileAttachment
from app.services.entity_extraction_service import EntityExtractionService
from app.services.agent_tools import AgentTools, TOOL_DEFINITIONS
from app.config import get_settings

settings = get_settings()


class AgenticChatService:
    """Agentic chat service with tool use and extended thinking"""

    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"
        self.extraction_service = EntityExtractionService()

    def process_message_agentic(
        self,
        db: Session,
        user_message: str,
        images: Optional[List[Dict[str, Any]]] = None,
        pdf_text: Optional[str] = None,
        file_metadata: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Process message with agentic behavior - SIMPLIFIED APPROACH.

        Phase 1: Ask Claude what tools it needs (with tools available)
        Phase 2: Execute those tools, show abbreviated results
        Phase 3: Stream the final response (without tools)

        This gives true real-time streaming for the final answer.
        """
        # Save user message
        user_msg = ChatMessage(
            role="user",
            content=user_message,
            message_type="pending"
        )
        db.add(user_msg)
        db.commit()

        # Handle file uploads
        if file_metadata:
            yield {"type": "thinking", "content": "Saving files and extracting information..."}
            content = user_message
            if pdf_text:
                content += f"\n\n[PDF Content]:\n{pdf_text}"

            journal_entry = JournalEntry(
                content=content,
                entry_date=date.today(),
                entry_type="document",
                is_processed=False
            )
            db.add(journal_entry)
            db.commit()
            db.refresh(journal_entry)

            for file_meta in file_metadata:
                attachment = FileAttachment(
                    journal_entry_id=journal_entry.id,
                    filename=file_meta["filename"],
                    file_type=file_meta["file_type"],
                    file_size=file_meta["file_size"],
                    file_path=file_meta["file_path"],
                    extracted_text=file_meta.get("extracted_text"),
                    description=file_meta.get("description")
                )
                db.add(attachment)
            db.commit()

            extraction_result = self.extraction_service.extract_and_save(db, journal_entry)
            yield {"type": "thinking", "content": f"✓ Files saved and indexed. Extracted {extraction_result.get('total_entities', 0)} entities."}

        # Initialize tools
        tools = AgentTools(db)
        message_content = self._build_message_content(user_message, images, pdf_text)
        recent_messages = self._get_recent_history(db)
        system_prompt = self._build_system_prompt()
        messages = recent_messages + [{"role": "user", "content": message_content}]

        # Start streaming immediately with tools available
        yield {"type": "thinking", "content": "Analyzing your question and planning how to answer it..."}

        # PHASE 1 & 2: Stream with tools - real-time tool detection
        tool_use_count = 0
        max_iterations = 10

        # Initial call - use blocking for simplicity but show progress
        # The streaming API doesn't actually help because we need the full response
        # to check stop_reason and extract tool calls
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )

        # PHASE 2: Tool Execution Loop (if tools were used)
        while response.stop_reason == "tool_use" and tool_use_count < max_iterations:
            tool_use_count += 1

            # Extract tool calls
            tool_uses = [block for block in response.content if block.type == "tool_use"]

            for tool_use_block in tool_uses:
                tool_name = tool_use_block.name

                # Show which tool we're using
                yield {
                    "type": "tool_use",
                    "tool_name": tool_name,
                    "content": f"Using {tool_name}..."
                }

            # Add assistant message with tool uses
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tools and collect results
            tool_results = []
            for tool_use_block in tool_uses:
                tool_name = tool_use_block.name
                tool_input = tool_use_block.input

                try:
                    tool_result = self._execute_tool(tools, tool_name, tool_input)
                    tool_result_content = json.dumps(tool_result, indent=2)

                    # Show abbreviated result to user
                    result_preview = self._abbreviate_tool_result(tool_name, tool_result)
                    yield {
                        "type": "thinking",
                        "content": result_preview
                    }

                except Exception as e:
                    tool_result_content = f"Error executing tool: {str(e)}"
                    yield {"type": "thinking", "content": f"⚠️ Error with {tool_name}"}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_block.id,
                    "content": tool_result_content
                })

            # Add tool results
            messages.append({"role": "user", "content": tool_results})

            # Check if Claude needs more tools
            yield {"type": "thinking", "content": "Analyzing results..."}

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

        # PHASE 3: Final Response - NOW STREAM IT!
        # No tools needed anymore, so we can stream the final answer
        yield {"type": "thinking", "content": "Generating response..."}

        final_response = ""

        # Make final call WITHOUT tools, WITH streaming
        with self.client.messages.stream(
            model=self.model,
            max_tokens=8192,
            system=system_prompt,
            messages=messages,
            # NO tools parameter = pure response streaming
        ) as stream:
            # Stream tokens as they arrive - TRUE real-time!
            for text in stream.text_stream:
                final_response += text
                yield {
                    "type": "response_chunk",
                    "content": text
                }

        # Handle brain dump processing
        is_brain_dump = self._is_brain_dump(user_message)
        extracted = False
        journal_created = False

        if is_brain_dump:
            yield {"type": "thinking", "content": "Extracting entities from your message..."}

            journal_entry = JournalEntry(
                content=user_message,
                entry_date=date.today(),
                entry_type="chat",
                is_processed=False
            )
            db.add(journal_entry)
            db.commit()
            db.refresh(journal_entry)

            extraction_result = self.extraction_service.extract_and_save(db, journal_entry)
            extracted = True
            journal_created = True

            extraction_summary = self._format_extraction_summary(extraction_result)
            final_response = f"{final_response}\n\n{extraction_summary}"

            yield {"type": "response_chunk", "content": f"\n\n{extraction_summary}"}

        # Save to database
        user_msg.message_type = "brain_dump" if is_brain_dump else "query"
        user_msg.extracted_entities = extracted
        user_msg.journal_entry_created = journal_created
        db.commit()

        assistant_msg = ChatMessage(
            role="assistant",
            content=final_response,
            message_type="brain_dump" if is_brain_dump else "query",
            extra_data={"tool_uses": tool_use_count}
        )
        db.add(assistant_msg)
        db.commit()

        # Final done signal
        yield {
            "type": "response_complete",
            "content": final_response,
            "message_type": "brain_dump" if is_brain_dump else "query",
            "extracted_entities": extracted,
            "journal_created": journal_created
        }

    def _abbreviate_tool_result(self, tool_name: str, result: Any) -> str:
        """Create abbreviated preview of tool results for user"""
        if isinstance(result, dict):
            if "error" in result:
                return f"⚠️ {tool_name}: {result['error']}"

            # Count items returned
            if "results" in result:
                count = len(result["results"])
                return f"✓ {tool_name}: Found {count} result(s)"
            elif "entries" in result:
                count = len(result["entries"])
                return f"✓ {tool_name}: Found {count} entr{'y' if count == 1 else 'ies'}"
            elif "people" in result:
                count = len(result["people"])
                return f"✓ {tool_name}: Found {count} person/people"
            else:
                return f"✓ {tool_name}: Completed"

        return f"✓ {tool_name}: Completed"

    def _build_message_content(
        self,
        text: str,
        images: Optional[List[Dict[str, Any]]] = None,
        pdf_text: Optional[str] = None
    ) -> List[Dict[str, Any]] | str:
        """Build message content with multimodal support"""
        if not images and not pdf_text:
            return text

        content = []
        if pdf_text:
            content.append({"type": "text", "text": f"{text}\n\n[PDF Content]:\n{pdf_text}"})
        else:
            content.append({"type": "text", "text": text})

        if images:
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img["media_type"],
                        "data": img["data"]
                    }
                })

        return content

    def _build_system_prompt(self) -> str:
        """Build system prompt for the agent"""
        return """You are CAiS Command Center, Zane's intelligent personal AI assistant with full access to his business journey.

You have access to tools to search and query Zane's complete history:
- Journal entries with detailed brain dumps
- People he's talked to (with context)
- Tasks and commitments
- Insights and realizations
- Challenges and blockers
- Wins and successes
- Topics and projects
- Previous chat conversations
- Uploaded documents (PDFs, images with extracted text/descriptions)

IMPORTANT INSTRUCTIONS:

1. **Be Thorough**: Don't rush to answer. Use tools to gather relevant context before responding.

2. **Multi-Step Reasoning**: For complex questions:
   - First search for relevant people/topics
   - Then get full journal entries for details
   - Analyze patterns across multiple sources
   - Synthesize a comprehensive answer

3. **Cite Sources**: Always reference where information came from ("In your entry from Jan 15..." or "When you talked to Sarah...")

4. **Tool Use Strategy**:
   - Use search_people to find who you're asking about
   - Use search_journal_entries to find relevant context
   - Use get_full_journal_entry to read complete entries
   - Use get_tasks/insights/challenges/wins for specific entity types
   - Use get_recent_activity for "what's happening" questions
   - Use search_documents to find previously uploaded PDFs or images

5. **Brain Dumps**: If the user is sharing what happened (not asking a question), respond conversationally. The system will automatically extract entities.

6. **Images & PDFs**: If images or PDFs are provided, analyze them in context of Zane's journey.

Be conversational, insightful, and act like a true AI sidekick that knows everything about Zane's business journey."""

    def _get_recent_history(self, db: Session, limit: int = 6) -> List[Dict[str, Any]]:
        """Get recent chat history for context"""
        recent = db.query(ChatMessage)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit)\
            .all()
        recent.reverse()

        return [{
            "role": msg.role,
            "content": msg.content
        } for msg in recent[-6:]]

    def _execute_tool(self, tools: AgentTools, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Execute a tool and return results"""
        method = getattr(tools, tool_name, None)
        if not method:
            return {"error": f"Tool {tool_name} not found"}

        return method(**tool_input)

    def _is_brain_dump(self, message: str) -> bool:
        """Detect if message is a brain dump vs query"""
        message_lower = message.lower()

        question_starts = ["what", "who", "when", "where", "how", "why", "which", "did i", "have i", "show me", "tell me", "find", "search"]
        if any(message_lower.startswith(q) for q in question_starts):
            return False

        if "?" in message:
            return False

        brain_dump_patterns = [
            "had a", "just had", "talked to", "spoke with", "met with",
            "i think", "i feel", "feeling", "realized", "noticed",
            "need to", "going to", "planning", "tomorrow", "next week",
            "built", "working on", "finished", "completed"
        ]
        if any(pattern in message_lower for pattern in brain_dump_patterns):
            return True

        return False

    def _format_extraction_summary(self, extraction_result: Dict[str, Any]) -> str:
        """Format extraction result into friendly summary"""
        parts = ["✓ I've captured that information:"]

        if extraction_result.get("people_count", 0) > 0:
            people = extraction_result.get("people", [])
            parts.append(f"\n👥 People: {', '.join(people)}")

        if extraction_result.get("tasks_count", 0) > 0:
            parts.append(f"\n✅ Added {extraction_result['tasks_count']} task(s)")

        if extraction_result.get("topics_count", 0) > 0:
            topics = extraction_result.get("topics", [])
            parts.append(f"\n📁 Topics: {', '.join(topics)}")

        if extraction_result.get("insights_count", 0) > 0:
            parts.append(f"\n💡 Captured {extraction_result['insights_count']} insight(s)")

        if extraction_result.get("wins_count", 0) > 0:
            parts.append(f"\n🎉 Logged {extraction_result['wins_count']} win(s)")

        if extraction_result.get("challenges_count", 0) > 0:
            parts.append(f"\n⚠️ Noted {extraction_result['challenges_count']} challenge(s)")

        return "".join(parts)
