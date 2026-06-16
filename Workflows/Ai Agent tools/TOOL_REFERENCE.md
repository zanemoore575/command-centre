# CAiS Memory Agent - Tool Reference

Base URL: `https://n8n-service-8act.onrender.com/webhook/`

All tools accept POST requests with JSON body.

---

## 0. Discover Database (USE FIRST!)

**Endpoint:** `tool-discover-database`

**Purpose:** Returns a comprehensive map of ALL data in the memory system - entity names, decision categories, reflection topics, customer names, themes, and more. **Use this FIRST when you don't know what to search for.**

**Parameters:** None required.

**Example Payload:**
```json
{}
```

**Returns:**
- All entity types and names (people, companies, projects, tools)
- Decision categories that exist
- Reflection topics and emotional tones
- Customer names with insights
- Strategic insight categories
- Main themes discussed
- Task categories and counts
- Memory statistics (total count, date range)

**When to Use:**
- At the start of a complex query
- When semantic search returns empty results
- When you're not sure what names/categories exist
- To verify exact spelling of entity names before searching

---

## 1. Semantic Search (PRIMARY TOOL)

**Endpoint:** `tool-semantic-search`

**Purpose:** Search memories by meaning/context. Combines embedding + vector search in one call.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | Yes | - | The search text |
| match_threshold | number | No | 0.35 | Similarity threshold (0.1-1.0, lower = more results) |
| match_count | number | No | 8 | Max results to return |

**Example Payloads:**
```json
// Basic search
{
  "query": "real estate investment strategy"
}

// More specific with parameters
{
  "query": "conversations with William about business",
  "match_threshold": 0.3,
  "match_count": 10
}

// Narrow search
{
  "query": "pricing model decision",
  "match_threshold": 0.5,
  "match_count": 5
}
```

---

## 2. Get Reflections

**Endpoint:** `tool-get-reflections`

**Purpose:** Retrieve personal reflections with emotional tone and topic.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| search_topic | string | No | null | Filter by topic keyword |
| recent_days | number | No | 365 | How far back to search |

**Example Payloads:**
```json
// All reflections from past year
{}

// Reflections about a specific topic
{
  "search_topic": "real estate"
}

// Recent reflections only
{
  "search_topic": null,
  "recent_days": 30
}

// Specific topic, recent only
{
  "search_topic": "business strategy",
  "recent_days": 90
}
```

---

## 3. Get Decisions

**Endpoint:** `tool-get-decisions`

**Purpose:** Retrieve past decisions with reasoning and category.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| search_topic | string | No | null | Filter by topic keyword |
| recent_days | number | No | 365 | How far back to search |

**Example Payloads:**
```json
// All decisions
{}

// Decisions about pricing
{
  "search_topic": "pricing"
}

// Recent business decisions
{
  "search_topic": "business",
  "recent_days": 60
}

// Technology decisions
{
  "search_topic": "tech stack"
}
```

---

## 4. Get Tasks

**Endpoint:** `tool-get-tasks`

**Purpose:** Retrieve tasks with urgency levels.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| task_status | string | No | "open" | Filter: "open", "completed", or "all" |

**Example Payloads:**
```json
// Open tasks (default)
{}

// Explicitly open tasks
{
  "task_status": "open"
}

// Completed tasks
{
  "task_status": "completed"
}

// All tasks regardless of status
{
  "task_status": "all"
}
```

---

## 5. Get Entity Details

**Endpoint:** `tool-get-entity-details`

**Purpose:** Get information about a person, company, tool, or project.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| search_name | string | Yes | - | Name to search for |

**Example Payloads:**
```json
// Search for a person
{
  "search_name": "William"
}

// Search for a company
{
  "search_name": "Anthropic"
}

// Search for a tool/project
{
  "search_name": "CAiS"
}

// Search with handle/nickname
{
  "search_name": "Greenmachine"
}
```

---

## 6. Memory Deep Dive

**Endpoint:** `tool-memory-deep-dive`

**Purpose:** Get FULL context for a specific memory including all related data.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| target_memory_id | number | Yes | - | The memory ID to deep dive |

**Example Payloads:**
```json
// Get full context for memory ID 42
{
  "target_memory_id": 42
}

// Alternative parameter name also works
{
  "memory_id": 15
}
```

**Note:** Use this after finding relevant memories via Semantic Search or Get Recent Memories.

---

## 7. Get Recent Memories

**Endpoint:** `tool-get-recent-memories`

**Purpose:** Get the most recent memories/conversations.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| limit_count | number | No | 10 | Number of memories to return (max 20) |
| filter_source | string | No | null | Filter by source type |

**Example Payloads:**
```json
// Last 10 memories (default)
{}

// Last 5 memories
{
  "limit_count": 5
}

// Only telegram conversations
{
  "filter_source": "telegram_conversation"
}

// Recent voice notes
{
  "filter_source": "voice",
  "limit_count": 10
}
```

---

## 8. Get Strategic Insights

**Endpoint:** `tool-get-strategic-insights`

**Purpose:** Get business/life strategy insights.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| search_category | string | No | null | Category filter |
| recent_days | number | No | 365 | How far back to search |

**Valid Categories:**
- `business_model`
- `positioning`
- `market_fit`
- `personal_growth`

**Example Payloads:**
```json
// All strategic insights
{}

// Business model insights
{
  "search_category": "business_model"
}

// Recent positioning insights
{
  "search_category": "positioning",
  "recent_days": 90
}

// Personal growth insights
{
  "search_category": "personal_growth"
}
```

---

## 9. Search by Theme

**Endpoint:** `tool-search-by-theme`

**Purpose:** Keyword-based search across memories. Good for broad topic searches.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| theme_keywords | string | Yes | - | Keywords to search |
| limit_count | number | No | 10 | Max results |

**Example Payloads:**
```json
// Search for a theme
{
  "theme_keywords": "real estate"
}

// Multiple keywords
{
  "theme_keywords": "AI automation tools"
}

// With limit
{
  "theme_keywords": "business strategy planning",
  "limit_count": 15
}
```

---

## 10. Get Customer Insights

**Endpoint:** `tool-get-customer-insights`

**Purpose:** Get customer/client feedback and insights.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| search_customer | string | No | null | Filter by customer name |

**Example Payloads:**
```json
// All customer insights
{}

// Specific customer
{
  "search_customer": "Acme Corp"
}

// Another customer
{
  "search_customer": "John Smith"
}
```

---

## Response Format

All tools return a consistent JSON structure:

```json
{
  "success": true,
  "count": 5,
  "tool": "tool_name",
  "message": "Found 5 results",
  "[results_array]": [...]
}
```

On error:
```json
{
  "success": false,
  "error": "Error description",
  "details": {...},
  "tool": "tool_name"
}
```

---

## Testing with cURL

```bash
# Test Discover Database (use this first!)
curl -X POST https://n8n-service-8act.onrender.com/webhook/tool-discover-database \
  -H "Content-Type: application/json" \
  -d '{}'

# Test Semantic Search
curl -X POST https://n8n-service-8act.onrender.com/webhook/tool-semantic-search \
  -H "Content-Type: application/json" \
  -d '{"query": "real estate strategy"}'

# Test Get Reflections
curl -X POST https://n8n-service-8act.onrender.com/webhook/tool-get-living-context \
  -H "Content-Type: application/json" \
  -d '{"p_user_id": "zane"}'

# Test Search by Theme
curl -X POST https://n8n-service-8act.onrender.com/webhook/tool-search-by-theme \
  -H "Content-Type: application/json" \
  -d '{"theme_keywords": "shopify", "limit_count": 10}'
```
