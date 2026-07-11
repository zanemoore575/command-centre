# Upgrade Instructions: Discovery Tool + Thorough Search Behavior

This document walks you through implementing Option 1 (Discovery Tool) and Option 3 (Better Empty Result Handling) to fix the "chicken and egg" problem with your AI agent.

---

## Overview of Changes

1. **New SQL Function**: `agent_discover_database()` - reveals what data exists
2. **New n8n Tool Workflow**: `tool_discover_database.json` - exposes the function as a tool
3. **Updated System Prompt**: `agent_system_prompt_v2.md` - teaches the agent to be thorough
4. **Main Workflow Update**: Add the discovery tool to the Memory Agent

---

## Step 1: Deploy the SQL Function

1. Open your Supabase Dashboard
2. Go to **SQL Editor**
3. Copy the contents of `agent_discovery_function.sql`
4. Run the SQL

**Test it works:**
```sql
SELECT * FROM agent_discover_database();
```

You should see rows showing your entity names, decision categories, reflection topics, etc.

---

## Step 2: Deploy the Tool Workflow

1. Open n8n
2. Create a **new workflow**
3. Import `Ai Agent tools/tool_discover_database.json`
4. Verify the Supabase credential is connected (`Zane.moore575 Supabase`)
5. **Activate** the workflow

**Test it works:**
```bash
curl -X POST https://n8n-service-8act.onrender.com/webhook/tool-discover-database \
  -H "Content-Type: application/json" \
  -d '{}'
```

You should get back a JSON with all your database contents mapped out.

---

## Step 3: Add the Tool to the Main Workflow

Open `telegram_cais_bot_workflow_agentic_v2.json` in n8n and:

### 3a. Add a new HTTP Request Tool node

1. Add a new **HTTP Request Tool** node
2. Configure it:

**Node Name:** `TOOL Discover Database`

**Settings:**
- Tool Description: `CRITICAL: Use this FIRST when you're unsure what data exists. Returns all entity names, decision categories, reflection topics, customer names, themes, and database statistics. Helps you know what to search for.`
- Method: `POST`
- URL: `https://n8n-service-8act.onrender.com/webhook/tool-discover-database`
- Send Body: Yes
- Body Parameters: (none needed, just send `{}`)

### 3b. Connect the tool to Memory Agent

Connect the `TOOL Discover Database` node's **ai_tool** output to the `Memory Agent` node's **ai_tool** input (same as the other tools).

---

## Step 4: Update the System Prompt

In the **Memory Agent** node, replace the System Message with the contents of `agent_system_prompt_v2.md`.

The key changes in the new prompt:
- **Discovery-first approach**: Agent learns to check what exists before searching
- **Empty result recovery**: Detailed instructions for what to do when searches fail
- **Multiple search strategies**: Try different phrasings, thresholds, and tools
- **Never give up**: Only say "I couldn't find anything" after exhausting alternatives

---

## Step 5: Test the Updated Agent

Send these test messages to your Telegram bot:

### Test 1: Discovery behavior
```
What data do you have about me?
```
The agent should call Discover Database and tell you about your entities, decisions, reflections, etc.

### Test 2: Entity lookup with wrong name
```
Tell me about Bill
```
If you have a "William" but no "Bill", the agent should:
1. Try Get Entity Details → empty
2. Call Discover Database → see "William"
3. Try Get Entity Details "William" → success
4. Report findings

### Test 3: Complex multi-part query
```
What decisions have I made about pricing, and who are the customers I've discussed this with?
```
The agent should:
1. Discover Database (see what categories/customers exist)
2. Get Decisions with topic="pricing"
3. Get Customer Insights
4. Semantic Search for connections
5. Synthesize a comprehensive answer

---

## Files Created/Modified

| File | Purpose | Status |
|------|---------|--------|
| `agent_discovery_function.sql` | SQL function for Supabase | NEW - Run in SQL Editor |
| `Ai Agent tools/tool_discover_database.json` | n8n workflow for tool | NEW - Import to n8n |
| `Ai Agent tools/TOOL_REFERENCE.md` | Updated documentation | UPDATED |
| `agent_system_prompt_v2.md` | New system prompt | NEW - Copy to Memory Agent |
| `telegram_cais_bot_workflow_agentic_v2.json` | Main workflow | NEEDS MANUAL UPDATE |

---

## Quick Reference: The New Tool

**Tool Name:** Discover Database

**When the Agent Should Use It:**
- At the start of complex queries
- When any search returns empty results
- When unsure about exact entity names
- When asked "what do you know about..."

**What It Returns:**
```json
{
  "entities": {
    "people": ["William", "Rachel", "Justin", "Aaron", ...],
    "companies": ["Anthropic", "Shopify", ...],
    "projects": ["Command Centre", "Rach-bot", ...],
    "tools": ["n8n", "Supabase", "OpenAI", ...]
  },
  "decisions": {
    "categories": ["pricing", "hiring", "tech_stack", ...]
  },
  "reflections": {
    "topics": ["business strategy", "personal growth", ...],
    "emotional_tones": ["optimistic", "frustrated", ...]
  },
  "customer_insights": {
    "customer_names": ["Justin", "Aaron", ...]
  },
  "strategic_insights": {
    "categories": ["business_model", "positioning", ...]
  },
  "themes": {
    "main_themes": ["AI automation", "real estate", ...]
  },
  "memories": {
    "statistics": ["Total: 47", "Date range: Jan 2024 - Jan 2026"]
  }
}
```

---

## Expected Behavior After Upgrade

**Before (the problem):**
```
User: "What did I discuss with Justin?"
Agent: Searches for "Justin" → Empty → "I don't have any records about Justin"
(But Justin is in the database as "Justin Smith")
```

**After (the fix):**
```
User: "What did I discuss with Justin?"
Agent:
1. Get Entity Details "Justin" → Empty
2. Discover Database → Sees "Justin Smith" in customer_names
3. Get Customer Insights "Justin" → Found 3 entries
4. Semantic Search "Justin" → Found 2 memories
5. Memory Deep Dive → Full context
6. "I found several discussions with Justin Smith..."
```

The agent becomes **thorough** instead of giving up after one failed search.
