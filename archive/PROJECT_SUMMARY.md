# Command Centre — Project Summary

> A personal AI-powered business intelligence system that knows your entire journey, never forgets context, and becomes smarter the more you use it.

---

## 1. The Problem This Solves

Every time you open a conversation with an AI assistant, you start from zero. You re-explain context, re-introduce people, re-state your goals. Important details from customer calls get forgotten. Commitments you made get lost. Patterns across dozens of conversations are invisible because they live scattered across voice memos, notebooks, and your own memory.

Command Centre exists to fix exactly this.

The name "CAiS" refers to Zane's startup journey — this system is the intelligence layer for that journey. The core insight driving the build is:

> "Stop starting fresh every conversation. Build a system that knows where you've been, where you are, and helps you get where you're going."

---

## 2. What the System Does

Command Centre is a **personal AI business intelligence system** with three core capabilities:

### 2.1 Capture Everything
You log thoughts, meetings, calls, realizations, and tasks in natural language — either by typing directly into the web app, or by speaking into your iPhone via a Shortcuts automation. The system accepts free-form "brain dumps" with no structure required.

### 2.2 Extract & Remember Automatically
When you submit a brain dump, Claude (Anthropic's AI) reads the text and automatically extracts structured data:
- **People** mentioned (and their company, role, context)
- **Tasks & commitments** (things you said you'd do, with priority)
- **Topics & projects** being worked on
- **Insights** — realizations and learnings
- **Events** — meetings, calls, milestones
- **Challenges** — blockers and problems
- **Wins** — successes and progress

This structured data is saved to a PostgreSQL database and indexed for retrieval.

### 2.3 Answer Questions From Your Own History
You can ask the AI anything about your history — "Who have I spoken to about construction?", "What were Matt's pain points?", "What tasks are still open?", "What patterns do you see across my discovery calls?" — and the AI searches your actual logged data to give you grounded, cited answers.

---

## 3. The Two Ways to Interact

### 3.1 Brain Dump (Input Mode)
You tell the system what happened. Example:

> "Just had a call with Matt from Auckland Construction. He's drowning in quote follow-ups, spending 10 hours a week chasing customers. Seemed really interested in automation. Need to follow up with a proposal by Friday."

The AI detects this is a brain dump (narrative/declarative tone, no question mark), saves it as a journal entry, and automatically extracts:
- Person: Matt, Auckland Construction
- Task: Follow up with proposal (high priority)
- Pain point: Quote follow-up (10 hrs/week)
- Topic: Trades automation

### 3.2 Query (Retrieval Mode)
You ask the system a question. Example:

> "What pain points have come up most in discovery calls?"

The AI detects this is a query, searches your journal entries using its tools, and synthesizes a response from your actual data — citing the specific entries where information came from.

The system auto-detects which mode you're in based on sentence structure (questions start with question words or contain "?", brain dumps are declarative/narrative).

---

## 4. iPhone Shortcuts Integration

A key input channel is iOS Shortcuts on Zane's iPhone. Because friction is the enemy of consistent logging — if capturing a thought takes more than 30 seconds, it won't happen — the iPhone integration makes voice logging zero-friction.

The workflow:
1. Trigger a Shortcut (e.g., from the home screen, widget, or "Hey Siri")
2. iPhone records a voice note
3. The Shortcut transcribes it (via iOS dictation or Whisper)
4. The transcribed text is sent as a POST request to the CAiS backend API (`/api/chat/messages/agentic`)
5. The system processes it as a brain dump — extracting entities, saving the journal entry, and storing all structured data

This means you can log a thought while driving, walking, or between meetings — the system captures and structures it without you ever opening a laptop.

---

## 5. Architecture Overview

```
iPhone Shortcut (voice → text)
        │
        ▼
Web App (Next.js)          ← also accepts typed input + file uploads
        │
        ▼ HTTP / SSE
FastAPI Backend (Python)
        │
        ├── Anthropic Claude API  ← AI brain (entity extraction + chat)
        │
        └── PostgreSQL Database   ← persistent memory
```

### 5.1 Backend — FastAPI (Python)
- **Framework**: FastAPI on Python 3.13
- **Database ORM**: SQLAlchemy with Alembic migrations
- **AI**: Anthropic Claude API (claude-sonnet-4-5)
- **Port**: 8000
- **Key files**:
  - `backend/app/main.py` — app entry point, CORS config, router wiring
  - `backend/app/api/chat_agentic.py` — main chat endpoint (streaming SSE)
  - `backend/app/api/journal.py` — journal CRUD endpoints
  - `backend/app/services/agentic_chat_service.py` — core AI orchestration
  - `backend/app/services/entity_extraction_service.py` — structured data extraction
  - `backend/app/services/agent_tools.py` — database query tools for the AI
  - `backend/app/models/` — all database models

### 5.2 Frontend — Next.js (TypeScript)
- **Framework**: Next.js 15 (App Router)
- **Styling**: Tailwind CSS
- **Port**: 3000 (or 3002 in development)
- **Key pages**:
  - `/` — dashboard / home with system status
  - `/chat` — main AI chat interface with streaming
  - `/journal` — list of all journal entries
  - `/journal/new` — create new journal entry
  - `/journal/[id]` — view a journal entry with extracted entities
  - `/journal/[id]/edit` — edit a journal entry

---

## 6. The AI Brain — How It Works

### 6.1 Three-Phase Agentic Chat

When you send a message, the backend orchestrates a **three-phase AI process** and streams each phase back to the frontend in real time using Server-Sent Events (SSE):

**Phase 1 — Planning (gray box in UI)**
Claude receives your message and decides what tools it needs to answer the question. This produces a thinking step visible in the UI.

**Phase 2 — Tool Execution (blue box in UI)**
Claude calls database query tools (defined in `agent_tools.py`) to fetch relevant information. The AI can chain multiple tool calls — e.g., first search people, then get full journal entries for those people. Tools available:
- `search_people` — find people by name or company
- `search_journal_entries` — keyword + date search across all entries
- `get_full_journal_entry` — fetch a complete entry with all its entities
- `get_tasks` — get commitments/action items (filterable by status, priority, person)
- `get_insights` — retrieve stored insights/realizations
- `get_challenges` — retrieve blockers
- `get_wins` — retrieve successes
- `get_topics` — retrieve topics and projects
- `get_recent_activity` — summary of what's happened in N days
- `search_chat_history` — search previous conversations
- `search_documents` — search uploaded PDFs and images

**Phase 3 — Final Response (white box in UI)**
Once tools have gathered all relevant context, Claude streams a synthesised answer word-by-word. This is true real-time streaming — you see the response appear as it's generated, not all at once.

### 6.2 Entity Extraction

When a brain dump is submitted (either via chat or as a journal entry), the `EntityExtractionService` calls Claude with a structured prompt to parse the raw text into typed entities. The AI returns JSON, which is then persisted across 8 related database tables. This happens automatically in the background — you just write naturally.

### 6.3 Brain Dump Detection

The system automatically distinguishes between a query (needs retrieval) and a brain dump (needs extraction + storage) using simple heuristics:
- Messages starting with "what", "who", "when", "where", "how", "why", "show me", "find" → query
- Messages containing "?" → query
- Messages containing phrases like "had a", "talked to", "realized", "need to", "built" → brain dump

---

## 7. Database Schema

All data is stored in PostgreSQL with the following core tables:

| Table | Purpose |
|---|---|
| `journal_entries` | Raw text content with date, type, mood, energy level |
| `people` | Contacts extracted from entries (name, company, role, mention count) |
| `commitments` | Tasks/action items linked to journal entries and people |
| `pain_points` | Customer pain points (legacy, kept for compatibility) |
| `entity_mentions` | Timeline linking any entity to the entry where it was mentioned |
| `topics` | Projects and topics discussed |
| `insights` | Realizations and learnings |
| `events` | Meetings, calls, milestones |
| `challenges` | Blockers and problems |
| `wins` | Successes and achievements |
| `chat_messages` | Full conversation history (user + assistant) |
| `file_attachments` | Uploaded PDFs and images with extracted text |

The `entity_mentions` table is the key relationship table — it creates a timeline of every entity (person, commitment, topic, etc.) across all journal entries, enabling queries like "show me every time Matt was mentioned and in what context."

---

## 8. File Upload Support

The chat interface (and via API, the iPhone Shortcuts workflow) supports uploading files alongside messages:
- **Images** — sent directly to Claude as base64 for visual analysis
- **PDFs** — text extracted via PyPDF2, passed to Claude as context

Uploaded files are:
1. Saved to disk in `backend/uploads/`
2. Linked to a journal entry in the database
3. Their extracted text is stored and indexed for future search via `search_documents`

---

## 9. Streaming UI — Phase-Separated Responses

The chat interface mirrors Claude Code's own UX — progressive disclosure of AI reasoning:

```
User sends message
       ↓
[Gray box]  PHASE 1: PLANNING
            💭 Analyzing your question...
       ↓
[Blue box]  PHASE 2: TOOL EXECUTION
            🔧 Using search_people...
            ✓ search_people: Found 3 people
            🔧 Using search_journal_entries...
            ✓ search_journal_entries: Found 12 entries
       ↓
[White box] PHASE 3: RESPONSE
            Based on your journal entries, you've talked to...
            [Streaming word by word with animated cursor]
       ↓
All three boxes collapse into a single saved message
```

Each phase renders in its own visually distinct card, appearing sequentially as the backend yields SSE events. This gives you live visibility into what the AI is doing, not a blank spinner followed by a wall of text.

---

## 10. Build History & Current State

The system was built in phases:

| Phase | Status | Description |
|---|---|---|
| 1 — Foundation | Complete | FastAPI backend, PostgreSQL, Next.js frontend, health checks |
| 2 — Journal System | Complete | Create/edit/view journal entries, pagination, search |
| 3 — Entity Extraction | Complete | Claude API integration, automatic extraction pipeline |
| 4 — Agentic Chat | Complete | Tool-use AI, multi-step reasoning, streaming SSE |
| 5 — People Tracking | Planned | People profiles, relationship timelines |
| 6 — Dashboard | Planned | Journey timeline, stats, visual progress |

**Active right now**: The core journal + chat system is fully functional. You can log brain dumps, ask questions, upload files, and get grounded AI responses from your own data.

---

## 11. Planned & Future Features

From the product vision, these are the next meaningful capabilities:

- **People profiles** — full page for each person with all mentions, context, and relationship timeline
- **Dashboard timeline** — visual journey showing key moments, wins, and milestones
- **Commitment tracking** — proactive reminders for things you said you'd do
- **Weekly digest** — automated summary of patterns, open tasks, and insights
- **Telegram bot** — send voice notes directly to Telegram for instant logging (currently approximated via iOS Shortcuts → API)
- **Gmail integration** — automatically capture client emails as journal entries
- **Calendar integration** — link meetings to journal entries, prompt for missing notes
- **Pattern recognition** — mood/energy/productivity analysis over time
- **Hypothesis tracking** — log beliefs, validate or invalidate with evidence

---

## 12. Running the System

### Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm run dev
```

### Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs

### Environment Variables
```
# backend/.env
DATABASE_URL=postgresql://user:password@localhost:5432/cais_command_center
ANTHROPIC_API_KEY=your_api_key_here
ENVIRONMENT=development

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 13. Design Principles

Seven principles guide every decision in this system:

1. **Friction-Free Input** — If logging takes more than 30 seconds, it won't happen. Voice-first, mobile-optimized, always accessible.
2. **Proactive Intelligence** — The system surfaces insights before you ask.
3. **Trust Through Accuracy** — Every insight is traceable to real data. No hallucinations, no generic advice.
4. **Integration Over Isolation** — Connect with tools already in use, don't create another silo.
5. **Show, Don't Tell** — Visualize progress and patterns; avoid walls of text.
6. **Respect My Time** — Notifications are meaningful and actionable, not spam.
7. **Learn From Me** — Gets smarter about Zane specifically over time.

---

## 14. The Dual Purpose

Command Centre serves two roles simultaneously:

1. **Personal tool** — Zane's own intelligence layer for the CAiS startup journey, tracking every conversation, commitment, insight, and win.

2. **Proof of concept** — A working demonstration of the exact kind of AI-powered system Zane builds and sells to trades businesses. Using your own tools is the strongest sales argument.

The "aha" moment the system is designed for:

> "I'm talking to Claude about a business decision. Instead of spending 10 minutes re-explaining context, I say 'check the Command Center' — and Claude can see my entire journey: every customer conversation, every hypothesis, every commitment, every win and struggle. The conversation starts from a place of deep understanding."

That's when this becomes indispensable.
