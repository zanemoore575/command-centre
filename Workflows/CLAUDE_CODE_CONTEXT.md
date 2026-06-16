# AI Brain Ingest - Project Context for Claude Code

> This document provides essential context for Claude Code when working on this project. Update this file as the system evolves.
>
> Primary project status is maintained in `../LIVING_DOC.md`. Use that file together with this context document when making progress updates or when working with Claude Code.

---

## Project Overview

**Purpose**: Personal AI memory system that captures conversations from Telegram, extracts insights, and enables semantic search across all stored knowledge.

**Architecture**: n8n workflows + Supabase (PostgreSQL + pgvector) + OpenAI APIs + Anthropic Claude + Telegram Bot

---

## Key Components

### Workflows (n8n)

| Workflow | File | Purpose |
|----------|------|---------|
| **Agentic Bot V2** | `telegram_cais_bot_workflow_agentic_v2.json` | **PRIMARY** - Claude Sonnet 4.5 with specialist agents and 5 tools |
| Timeout Handler | `telegram_session_timeout_handler_workflow.json` | Auto-saves inactive sessions (30 min timeout), runs every 5 min |
| Ingestion Pipeline | `ingest-workflow.json` | Extracts entities, decisions, reflections from transcripts. Two entry points: `/webhook/ingest-conversation` (voice path, inserts a new row) and `/webhook/ingest-pending` (poller path, updates an existing row in place) — both converge into the same extraction/embedding nodes |
| Shortcut Voice | `shortcut_voicenote_workflow.json` | iOS Shortcut voice note ingestion |
| **Pending Memory Poller** | `pending-memory-poller-workflow.json` | **NEW (2026-06-17)** - Runs every 2 min, finds any `memories` row stuck at `status='pending'` (e.g. from `log_memory`), claims it, and routes it into the ingestion pipeline via `/webhook/ingest-pending`. Makes ingestion source-agnostic — any future write path just needs to insert with `status: pending` |

### AI Agent Tools (n8n Workflows)

Located in `/Ai Agent tools/` directory:

| Tool | File | Purpose |
|------|------|---------|
| **Discover Database** | `tool_discover_database.json` | **NEW** - Returns all available entity names, categories, themes, stats |
| Semantic Search | `tool_semantic_search.json` | Vector embedding search across memories |
| Get Entity Details | `tool_get_entity_details.json` | Look up people, companies, projects, tools |
| Get Decisions | `tool_get_decisions.json` | Retrieve past decisions with reasoning |
| Get Reflections | `tool_get_reflections.json` | Access personal insights and breakthroughs |
| Get Tasks | `tool_get_tasks.json` | Retrieve action items with urgency levels |
| Get Recent Memories | `tool_get_recent_memories.json` | Browse latest conversations |
| Get Strategic Insights | `tool_get_strategic_insights.json` | Business strategy patterns by category |
| Get Customer Insights | `tool_get_customer_insights.json` | Client feedback and pain points |
| Memory Deep Dive | `tool_memory_deep_dive.json` | Full context for specific memory |
| Search by Theme | `tool_search_by_theme.json` | Keyword-based theme search |

### Database (Supabase)

**Project URL**: `https://wwqdkiphfpdczgmnxxrt.supabase.co`

#### Core Tables

```
telegram_sessions
├── id (UUID, PRIMARY KEY)
├── chat_id (BIGINT) - Telegram chat identifier
├── started_at (TIMESTAMPTZ)
├── last_activity (TIMESTAMPTZ)
├── messages (JSONB) - Array of {role, content}
├── status (TEXT) - 'active' | 'cleared' | 'abandoned' | 'completed' | 'timed_out'
└── memory_id (BIGINT, FK → memories.id)

memories
├── id (BIGINT, AUTO)
├── source (TEXT) - 'telegram_conversation' | 'telegram_conversation_auto' | 'chatgpt_import'
├── transcript (TEXT)
├── title (TEXT)
├── summary (TEXT)
├── status (TEXT) - 'pending' | 'processing' | 'completed'
├── embeddings (VECTOR(1536))  -- NOTE: plural column name!
└── created_at (TIMESTAMPTZ)

entities
├── memory_id (FK)
├── entity_type (TEXT) - 'person' | 'company' | 'project' | 'tool' | 'concept'
├── entity_name (TEXT)
└── context (TEXT)

decisions
├── memory_id (FK)
├── decision (TEXT)
├── category (TEXT)
├── reasoning (TEXT)
├── confidence_level (TEXT)
└── emotional_context (TEXT)

reflections
├── memory_id (FK)
├── reflection (TEXT)
├── reflection_type (TEXT)
├── topic (TEXT)
└── emotional_tone (TEXT)

strategic_insights
├── memory_id (FK)
├── insight (TEXT)
├── insight_category (TEXT) - 'business_model' | 'positioning' | 'market_fit' | 'personal_growth'
├── confidence (TEXT)
└── suggested_action (TEXT)

customer_insights
├── memory_id (FK)
├── customer_name (TEXT)
├── customer_type (TEXT)
├── pain_point (TEXT)
├── desire (TEXT)
└── quote (TEXT)

tasks
├── memory_id (FK)
├── task (TEXT)
├── urgency (TEXT) - 'immediate' | 'this_week' | 'soon' | 'someday'
├── category (TEXT)
├── completed (BOOLEAN)
└── completed_at (TIMESTAMPTZ)

themes
├── memory_id (FK)
├── main_theme (TEXT)
├── sub_themes (JSONB)
├── conversation_type (TEXT)
└── key_takeaways (JSONB)
```

#### RPC Functions

**Session Management:**
```sql
get_or_create_session(p_chat_id BIGINT) → telegram_sessions
append_session_message(p_session_id UUID, p_role TEXT, p_content TEXT) → void
compile_session_transcript(p_session_id UUID) → TEXT
```

**Agent Tools:**
```sql
agent_discover_database() → TABLE  -- NEW: Returns all available data categories
agent_search_memories_by_embedding(query_embedding, match_threshold, match_count) → TABLE
agent_get_entity_details(search_name TEXT) → TABLE
agent_get_decisions(search_topic TEXT, recent_days INT) → TABLE
agent_get_reflections(search_topic TEXT, recent_days INT) → TABLE
agent_get_tasks(task_status TEXT) → TABLE
agent_get_strategic_insights(search_category TEXT, recent_days INT) → TABLE
agent_get_customer_insights(search_customer TEXT) → TABLE
agent_get_memory_context(target_memory_id BIGINT) → TABLE  -- Full deep dive
agent_get_recent_memories(limit_count INT, filter_source TEXT) → TABLE
agent_search_by_theme(theme_keywords TEXT, limit_count INT) → TABLE
```

**SQL Files:**
- `supabase_rpc_functions.sql` - Core session functions
- `supabase_agent_tools.sql` - Agent tool functions (10 tools)
- `agent_discovery_function.sql` - **NEW** Discovery tool function

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/end` | Save current conversation & extract insights |
| `/clear` | Discard current conversation (no save) |
| `/new` | Abandon current session, start fresh |
| `/tasks` | Show open tasks from extracted insights |
| `/recent` | Show recent memories with stats |
| `/help` | Display command menu |

---

## Credentials (n8n IDs)

| Credential | ID | Name |
|------------|-----|------|
| Supabase | `WLH1xOtq0dhre1iC` | Zane.moore575 Supabase |
| Telegram (Main) | `2ziiRMC49o7x8dzx` | Command Centre Bot |
| OpenAI | `pDJOyVluHP4GnR2q` | OpenAi account |
| Anthropic | `6AhJQz2ZKkf4Ce3r` | Anthropic account |

---

## External Services

| Service | URL | Purpose |
|---------|-----|---------|
| n8n Instance | `https://n8n-service-8act.onrender.com` | Workflow hosting |
| Tool Webhooks | `/webhook/tool-*` | AI Agent tool endpoints |
| Ingest Webhook | `/webhook/ingest-conversation` | Extraction pipeline trigger (voice path — inserts new row) |
| Ingest Webhook (pending) | `/webhook/ingest-pending` | Extraction pipeline trigger (poller path — updates existing row) |

---

## Agentic Architecture

### How It Works

The agentic bot uses n8n's AI Agent node with **Claude Sonnet 4.5** and a **hierarchical specialist agent system**:

```
┌─────────────────────────────────────────────────────────────┐
│                    HIERARCHICAL AGENT SYSTEM                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │               MAIN AGENT (Sonnet 4.5)                │   │
│  │  - Orchestrates conversation                         │   │
│  │  - Calls specialist agents as tools                  │   │
│  │  - Synthesizes final response                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│           ┌───────────────┼───────────────┐                 │
│           ▼               ▼               ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  MEMORY     │  │  ENTITY     │  │  STRATEGY   │         │
│  │  SPECIALIST │  │  SPECIALIST │  │  SPECIALIST │         │
│  │ (GPT-4o-m)  │  │ (GPT-4o-m)  │  │ (GPT-4o-m)  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│        │                │                │                  │
│        ▼                ▼                ▼                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              RAW TOOLS (11 n8n webhooks)              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Main Agent Tools (5 Total)

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **Discover Database** | Returns ALL entity names, categories, themes, stats | **USE FIRST** when unsure what data exists |
| **Memory Specialist** | Searches, retrieves, and synthesizes memories | Any question about past conversations |
| **Entity Specialist** | Builds profiles of people, companies, projects | "Tell me about [person/company]" |
| **Strategy Specialist** | Synthesizes decisions, insights, reflections | "What did I decide...", strategy questions |
| **Get Tasks** | Retrieve action items with urgency | "What do I need to do" |

### Specialist Agents (Sub-agents with AI Agent nodes)

Each specialist is a separate n8n workflow with its own AI Agent (GPT-4o-mini) and access to multiple raw tools:

**Memory Specialist** (`specialist-memory`):
- Semantic Search, Recent Memories, Theme Search, Memory Deep Dive
- Returns synthesized memory context with relevance scores

**Entity Specialist** (`specialist-entity`):
- Entity Details, Customer Insights, Semantic Search, Memory Deep Dive
- Returns complete profiles of people/companies

**Strategy Specialist** (`specialist-strategy`):
- Decisions, Reflections, Strategic Insights, Semantic Search, Memory Deep Dive
- Returns strategic synthesis with decision history

### Living Context Document

The system maintains a **Living Context Document** that persists across conversations:

```sql
living_context
├── user_id (TEXT) - 'zane'
├── business_hypotheses (JSONB) - Current working theories
├── directional_summary (JSONB) - Where things are heading
├── patterns (JSONB) - Repeated behaviors/blockers/energizers
├── identity_notes (JSONB) - Skills compounding, values emerging
├── active_threads (TEXT[]) - Current focus areas
└── updated_at (TIMESTAMPTZ)
```

**Fetched at start of every conversation** → Gives agent persistent context
**Updated after /end** → AI analyzes conversation and updates relevant fields

### Telegram HTML Formatting

Responses are automatically converted from Markdown to Telegram HTML:

```javascript
// In "Chunk & Format Response" node
- **bold** → <b>bold</b>
- *italic* → <i>italic</i>
- `code` → <code>code</code>
- ```blocks``` → <pre>blocks</pre>
- [links](url) → <a href="url">links</a>
- # Headers → <b>Headers</b>
```

Send Response node uses `parse_mode: "HTML"`

---

## Data Flow: Message → Memory

### Agentic Flow (telegram_cais_bot_workflow_agentic_v2.json)
```
1. Telegram message received
2. Session retrieved/created (get_or_create_session)
3. User message appended to session
4. "Searching my memory banks..." indicator sent
5. AI AGENT LOOP BEGINS:
   ├── Agent analyzes question
   ├── Agent calls Discover Database (if complex query)
   ├── Agent calls relevant search tools
   ├── Agent evaluates: "Do I have enough context?"
   ├── If no → call more tools (loop continues)
   └── If yes → generate final response
6. Response chunked if >4000 chars (Telegram limit)
7. Response appended to session
8. Response sent to Telegram
```

### On /end or timeout:
```
9. Transcript compiled from messages
10. Memory record created (status='pending')
11. Extraction pipeline called (webhook)
12. Entities, decisions, reflections, tasks extracted
13. Embeddings generated (text-embedding-3-small)
14. Memory status → 'completed'
15. Session status → 'completed' or 'timed_out'
```

### Claude write flow (`log_memory` MCP tool) — fixed 2026-06-17
```
1. Claude calls log_memory(content) via the MCP server
2. tool_log_memory() inserts directly into `memories` (status='pending')
   — MCP server has no n8n credentials, so it cannot call the ingest
     webhook itself; it only ever writes the row
3. Pending Memory Poller (runs every 2 min) selects status='pending' rows
4. Poller immediately sets status='claimed' (closes the race window —
   n8n webhooks ack instantly, so without this a slow extraction run
   could get picked up twice by the next poll)
5. Poller POSTs {memory_id, transcript, title, source} to
   /webhook/ingest-pending
6. ingest-workflow.json's "Update Memory To Extracting" node updates the
   SAME row (status='extracting') instead of inserting a duplicate
7. Same extraction/embedding nodes as the voice path run
8. Memory status → 'completed', embeddings populated
```
Voice notes and Claude writes now both terminate in the same extraction
pipeline — the only difference is which webhook gets called and whether
the row is inserted (voice) or updated in place (Claude/poller).

---

## Files in This Project

```
AI_Brain_Ingest/
├── telegram_cais_bot_workflow_agentic_v2.json  # PRIMARY: Agentic bot workflow
├── telegram_session_timeout_handler_workflow.json
├── ingest-workflow.json
├── pending-memory-poller-workflow.json         # NEW: picks up any status='pending' row
├── shortcut_voicenote_workflow.json
├── backfill_embeddings.py                      # NEW: one-time embedding backfill script
├── supabase_agent_tools.sql                    # 10 agent tool RPC functions
├── agent_discovery_function.sql                # NEW: Discovery tool SQL
├── agent_system_prompt.md                      # System prompt for agent
├── agent_system_prompt_v2.md                   # Backup/reference prompt
├── database_information.json                   # Full database schema
├── upload_history.py                           # ChatGPT export importer
├── conversations.json                          # ChatGPT export data
├── CLAUDE_CODE_CONTEXT.md                      # This file
├── UPGRADE_INSTRUCTIONS.md                     # Setup guide for discovery tool
│
└── Ai Agent tools/
    ├── TOOL_REFERENCE.md                       # Complete API reference
    ├── tool_discover_database.json             # NEW: Discovery tool workflow
    ├── tool_semantic_search.json
    ├── tool_get_entity_details.json
    ├── tool_get_decisions.json
    ├── tool_get_reflections.json
    ├── tool_get_tasks.json
    ├── tool_get_recent_memories.json
    ├── tool_get_strategic_insights.json
    ├── tool_get_customer_insights.json
    ├── tool_memory_deep_dive.json
    └── tool_search_by_theme.json
```

---

## Recent Achievements (Changelog)

### 2026-06-17: Fixed write/ingest path for Claude (`log_memory`) writes

**Problem Solved**: Memories written via Claude's `log_memory` MCP tool (`backend/app/mcp/supabase_tools.py`) inserted directly into `memories` with `status='pending'` but nothing ever called the n8n extraction webhook — only the voice-note path did. Pending rows sat unprocessed forever: no entities/themes/embeddings, invisible to `get_recent_memories` and `search_memories`. This was also the root cause of `search_memories` appearing to return no results for real content (e.g. "Jake") — affected memories simply never reached `status='completed'`.

**Solution Implemented**:
1. **New `pending-memory-poller-workflow.json`** — schedule-triggered every 2 min, selects any `memories` row with `status='pending'`, claims it (`status='claimed'`) to avoid double-processing, then calls the extraction pipeline. Source-agnostic by design: works for `log_memory`, voice notes, or any future write path without per-source code changes.
2. **New webhook entry point in `ingest-workflow.json`** (`Webhook Pending` → `Update Memory To Extracting`) — updates the existing row in place instead of inserting a duplicate, then reuses the same 7 extraction branches + embedding step the voice path already used. The original `/webhook/ingest-conversation` voice path is unchanged.
3. **Fixed embedding bug** — "Insert Embeddings" node was `JSON.stringify`-ing the embedding array before writing to the pgvector column; now passes the raw array (matches the working voice-path node).
4. **`backfill_embeddings.py`** — one-time script to embed existing `completed` memories that had `embeddings: null`.

**Verified**: test memory went `pending` → fully extracted → embedded → searchable within minutes. Pre-existing search gaps (e.g. "Jake") resolved. Embedding count went from ~2 to parity with completed-memory count.

**Key Files Changed**:
- `Workflows/n8n workflows/ingest-workflow.json` (UPDATED — new webhook entry point + embedding fix)
- `Workflows/n8n workflows/pending-memory-poller-workflow.json` (NEW)
- `Workflows/backfill_embeddings.py` (NEW)

### 2026-01-22: Hierarchical Specialist Agent System + Living Context

**Problem Solved**: Token limit issues (hitting 200k-400k limits) due to too much raw context being fed to main agent.

**Solution Implemented**:
1. **Hierarchical Agent Architecture** - Main agent calls specialist sub-agents instead of raw tools
   - Specialists pre-filter and synthesize information
   - Reduces token usage by returning summaries instead of raw data
   - Each specialist is an AI Agent node (GPT-4o-mini) with access to multiple tools

2. **Living Context Document** - Persistent context across conversations
   - Created `living_context` table and `update_living_context` RPC function
   - Fetched at start of every conversation
   - Updated after `/end` command via AI analysis of transcript
   - Fields: business_hypotheses, directional_summary, patterns, identity_notes, active_threads

3. **Model Change** - Switched from Claude Opus 4.5 to **Sonnet 4.5** (without extended thinking)
   - Extended thinking caused errors with tool calling in n8n
   - Sonnet 4.5 provides good balance of quality and compatibility

4. **Telegram HTML Formatting** - Proper formatting in Telegram messages
   - Added Markdown-to-HTML conversion in "Chunk & Format Response" node
   - Send Response node uses `parse_mode: "HTML"`

**Key Files Changed**:
- `telegram_cais_bot_workflow_agentic_v2.json` (UPDATED - new architecture)
- Specialist workflows (TO CREATE): `specialist-memory`, `specialist-entity`, `specialist-strategy`
- `living_context` SQL table and functions (TO CREATE in Supabase)
- `tool_get_living_context.json` (TO CREATE)

### 2026-01-19: Discovery Tool + Thorough Search Behavior

**Problem Solved**: "Chicken and Egg" issue where the agent didn't know what to query, so it guessed wrong and assumed no data existed.

**Solution Implemented**:
1. **Created `agent_discover_database()` SQL function** - Returns comprehensive overview of all data in the system (entity names, categories, themes, stats)
2. **Created `tool_discover_database.json` workflow** - Exposes discovery function as an agent tool
3. **Updated `agent_system_prompt.md`** - Teaches agent to:
   - Use Discovery first for complex queries
   - Never give up after one empty result
   - Try alternative phrasings and tools
   - Check exact entity name spellings via Discovery
4. **Updated `TOOL_REFERENCE.md`** - Added Discovery as Tool #0

**Key Files Changed**:
- `agent_discovery_function.sql` (NEW)
- `Ai Agent tools/tool_discover_database.json` (NEW)
- `agent_system_prompt.md` (UPDATED with thorough search behavior)
- `Ai Agent tools/TOOL_REFERENCE.md` (UPDATED)
- `UPGRADE_INSTRUCTIONS.md` (NEW - deployment guide)

### 2026-01-18: Initial Agentic System

- Created agentic bot with Claude Opus 4.5 and 10 custom tools
- Built all tool workflows and SQL functions
- Implemented session management and extraction pipeline

---

## Common Issues & Solutions

### Issue: Discovery tool returns "column status does not exist"
**Solution**: The `tasks` table uses `completed` (boolean), not `status`. Fixed in `agent_discovery_function.sql` - re-run the SQL.

### Issue: Agent doesn't use Discovery tool
**Solution**:
1. Verify `TOOL Discover Database` node exists in workflow
2. Verify its `ai_tool` output is connected to Memory Agent's `ai_tool` input
3. Verify system prompt mentions Discover Database

### Issue: Supabase RPC returns 404
**Solution**: RPC function doesn't exist. Run the appropriate SQL file in Supabase SQL Editor.

### Issue: Memory search returns no results
**Check**:
1. Memories exist with `embeddings` column populated (note: plural!)
2. `match_threshold` isn't too high (try 0.3-0.5)
3. pgvector extension is enabled in Supabase
4. The memory's `status` actually reached `'completed'` — `agent_search_by_theme` and `agent_get_recent_memories` both filter on `status='completed'`. If a memory is stuck at `'pending'`, check that the Pending Memory Poller workflow is active in n8n and that `/webhook/ingest-pending` is reachable (see 2026-06-17 changelog entry)

### Issue: A memory written via `log_memory` never shows up in search or recent memories
**Solution**: `log_memory` only inserts the row (`status='pending'`) — it does not call the ingest webhook directly. Confirm the `pending-memory-poller-workflow.json` workflow is **active** in n8n; it runs every 2 minutes and is what actually triggers extraction for these rows. Check its execution history for failures if a memory has been stuck at `'pending'` or `'claimed'` for more than a few minutes.

### Issue: Agent gives up too quickly on searches
**Solution**: Update system prompt with thorough search behavior (see `agent_system_prompt.md`)

---

## Testing Commands

### Test Discovery Tool
```bash
curl -X POST https://n8n-service-8act.onrender.com/webhook/tool-discover-database \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Test Semantic Search
```bash
curl -X POST https://n8n-service-8act.onrender.com/webhook/tool-semantic-search \
  -H "Content-Type: application/json" \
  -d '{"query": "business strategy"}'
```

### Test Complex Query via Telegram
```
I need a full status update. First, show me what data you have access to - what people, companies, projects, and topics are in your memory? Then, based on what you find, tell me about the most frequently mentioned person and any decisions I've made involving them.
```

---

## Future Enhancements (Ideas)

- [x] **Agentic context gathering** - AI agent with tool-calling
- [x] **Discovery tool** - Agent can see what data exists before searching
- [x] **Thorough search behavior** - Agent doesn't give up after one empty result
- [x] **Hierarchical specialist agents** - Pre-filter and synthesize context
- [x] **Living Context Document** - Persistent beliefs/patterns across conversations
- [x] **Telegram HTML formatting** - Proper bold, italic, code rendering
- [ ] Build specialist agent workflows (Memory, Entity, Strategy)
- [ ] Add `/summary` command for daily/weekly summaries
- [ ] Implement conversation threading for long sessions
- [ ] Add file/image attachment handling
- [ ] Create web dashboard for memory browsing
- [ ] Add scheduled reflection prompts
- [ ] Implement memory consolidation (merge similar memories)

---

## Last Updated

**Date**: 2026-06-17
**By**: Claude Code
**Changes**:
- Fixed write/ingest path so `log_memory` (Claude) writes get processed like voice notes
- Added `pending-memory-poller-workflow.json` (source-agnostic ingestion trigger)
- Added second webhook entry point to `ingest-workflow.json` (update-in-place, no duplicate rows)
- Fixed embedding `JSON.stringify` bug in ingest pipeline
- Added `backfill_embeddings.py` for one-time embedding backfill
