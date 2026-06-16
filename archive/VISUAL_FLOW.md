# Visual Flow: Phase-Separated Streaming

## The Three Boxes

```
┌──────────────────────────────────────────────────────────────┐
│                         USER MESSAGE                         │
│  "Who have I talked to about construction?"                  │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ ████████████████ PHASE 1: PLANNING ████████████████          │
│ ──────────────────────────────────────────────────────────   │
│ 💭 Analyzing your question and planning how to answer it... │
│                                                               │
│ [Gray background, appears at T+500ms]                        │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ ████████████ PHASE 2: TOOL EXECUTION ████████████            │
│ ──────────────────────────────────────────────────────────   │
│ 🔧 Using search_people...                                    │
│ 🔧 Using search_journal_entries...                           │
│                                                               │
│ ✓ search_people: Found 3 people                             │
│ ✓ search_journal_entries: Found 12 entries                  │
│                                                               │
│ [Blue background, appears at T+1000ms]                       │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ ████████████████ PHASE 3: RESPONSE ████████████████          │
│ ──────────────────────────────────────────────────────────   │
│ Based on your journal entries, you've talked to several     │
│ people about construction:                                   │
│                                                               │
│ 1. **John Smith** - Discussed foundation work and budget    │
│    concerns. He mentioned the timeline is tight...           │
│                                                               │
│ 2. **Sarah Johnson** - Talked about materials sourcing...█  │
│    [Streaming word by word with animated cursor]             │
│                                                               │
│ [White background, appears at T+4000ms]                      │
└──────────────────────────────────────────────────────────────┘
```

## Timeline Visualization

```
Time    Phase 1 (Gray)    Phase 2 (Blue)    Phase 3 (White)
────────────────────────────────────────────────────────────
0ms     [Empty]           [Not visible]      [Not visible]
500ms   [Starting...]     [Not visible]      [Not visible]
1000ms  [Analyzing...]    [Empty]            [Not visible]
1500ms  [Analyzing...]    [Tool 1...]        [Not visible]
2000ms  [Analyzing...]    [✓ Tool 1]         [Not visible]
2500ms  [Analyzing...]    [Tool 2...]        [Not visible]
3000ms  [Analyzing...]    [✓ Tool 1,2]       [Not visible]
4000ms  [Analyzing...]    [✓ Tool 1,2]       [Empty]
4100ms  [Analyzing...]    [✓ Tool 1,2]       [Based]
4200ms  [Analyzing...]    [✓ Tool 1,2]       [Based on]
4300ms  [Analyzing...]    [✓ Tool 1,2]       [Based on your]
...     [Analyzing...]    [✓ Tool 1,2]       [Streaming...]
10000ms [Complete]        [Complete]         [Complete]
        ↓                 ↓                  ↓
        All three boxes collapse into saved message
```

## State Flow Diagram

```
                    sendMessage()
                         │
                         ▼
              ┌──────────────────────┐
              │ Reset All Phase      │
              │ States               │
              │ - phase1Thinking=[]  │
              │ - phase2Tools=[]     │
              │ - phase2Results=[]   │
              │ - phase3Response=''  │
              │ - currentPhase=1     │
              └──────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ SSE Stream Starts    │
              └──────────────────────┘
                         │
                         ▼
         ╔═══════════════════════════════╗
         ║ Event: type="thinking"        ║
         ║ !inToolPhase = true           ║
         ╚═══════════════════════════════╝
                         │
                         ▼
         ┌───────────────────────────────┐
         │ phase1Thinking.push(content)  │
         │ → Gray box appears/updates    │
         └───────────────────────────────┘
                         │
                         ▼
         ╔═══════════════════════════════╗
         ║ Event: type="tool_use"        ║
         ║ inToolPhase → true            ║
         ║ currentPhase → 2              ║
         ╚═══════════════════════════════╝
                         │
                         ▼
         ┌───────────────────────────────┐
         │ phase2Tools.push(content)     │
         │ → Blue box appears            │
         └───────────────────────────────┘
                         │
                         ▼
         ╔═══════════════════════════════╗
         ║ Event: type="thinking"        ║
         ║ inToolPhase = true            ║
         ╚═══════════════════════════════╝
                         │
                         ▼
         ┌───────────────────────────────┐
         │ phase2Results.push(content)   │
         │ → Blue box updates (results)  │
         └───────────────────────────────┘
                         │
                         ▼
         ╔═══════════════════════════════╗
         ║ Event: type="response_chunk"  ║
         ║ currentPhase → 3              ║
         ╚═══════════════════════════════╝
                         │
                         ▼
         ┌───────────────────────────────┐
         │ phase3Response += content     │
         │ → White box appears/updates   │
         │ → Text streams word by word   │
         └───────────────────────────────┘
                         │
                         ▼
         ╔═══════════════════════════════╗
         ║ Stream Complete               ║
         ╚═══════════════════════════════╝
                         │
                         ▼
         ┌───────────────────────────────┐
         │ Combine all phases            │
         │ Create saved message          │
         │ Reset phase states            │
         │ Three boxes disappear         │
         └───────────────────────────────┘
```

## Component Hierarchy

```
ChatPage
  │
  ├─ messages.map() → MessageComponent
  │   └─ [Previous saved messages]
  │
  ├─ {loading && phase1Thinking.length > 0}
  │   └─ Phase 1 Box (Gray)
  │       ├─ Label: "PHASE 1: PLANNING"
  │       └─ phase1Thinking.map()
  │           └─ 💭 Thinking steps
  │
  ├─ {loading && (phase2Tools.length > 0 || phase2Results.length > 0)}
  │   └─ Phase 2 Box (Blue)
  │       ├─ Label: "PHASE 2: TOOL EXECUTION"
  │       ├─ phase2Tools.map()
  │       │   └─ 🔧 Tool badges
  │       └─ phase2Results.map()
  │           └─ ✓ Results
  │
  └─ {loading && phase3Response}
      └─ Phase 3 Box (White)
          ├─ Label: "PHASE 3: RESPONSE"
          ├─ <ReactMarkdown>{phase3Response}</ReactMarkdown>
          └─ Animated cursor (█)
```

## Event Routing Logic

```
SSE Event Type      inToolPhase     Action
─────────────────────────────────────────────────────
thinking            false        → phase1Thinking
thinking            true         → phase2Results
tool_use            *            → phase2Tools, set inToolPhase=true
response_chunk      *            → phase3Response
response_complete   *            → finalize
```

## Visual Styling Reference

```css
Phase 1 (Gray Box):
┌──────────────────────────────────────┐
│ bg-gray-50                           │
│ border-l-4 border-gray-400           │
│ rounded-lg px-4 py-3                 │
│                                      │
│ Label: text-xs text-gray-500         │
│ Content: text-sm text-gray-700       │
│ Emoji: opacity-50                    │
└──────────────────────────────────────┘

Phase 2 (Blue Box):
┌──────────────────────────────────────┐
│ bg-blue-50                           │
│ border-l-4 border-blue-500           │
│ rounded-lg px-4 py-3                 │
│                                      │
│ Label: text-xs text-blue-700         │
│ Tools: bg-blue-100 border-blue-300   │
│ Results: text-green-700              │
└──────────────────────────────────────┘

Phase 3 (White Box):
┌──────────────────────────────────────┐
│ bg-white                             │
│ border border-gray-200               │
│ rounded-lg px-4 py-3                 │
│                                      │
│ Label: text-xs text-gray-500         │
│ Content: prose prose-sm              │
│ Cursor: bg-blue-600 animate-pulse    │
└──────────────────────────────────────┘
```

## Real-World Example

### User Question
```
"What patterns do you see in my conversations with construction people?"
```

### Phase 1: Planning (Gray Box) - 500ms
```
┌────────────────────────────────────────────────┐
│ PHASE 1: PLANNING                              │
│ ────────────────────────────────────────────── │
│ 💭 Analyzing your question and planning how   │
│    to answer it...                             │
└────────────────────────────────────────────────┘
```

### Phase 2: Tool Execution (Blue Box) - 1000-3500ms
```
┌────────────────────────────────────────────────┐
│ PHASE 2: TOOL EXECUTION                        │
│ ────────────────────────────────────────────── │
│ 🔧 Using search_people...                      │
│ 🔧 Using search_journal_entries...             │
│                                                │
│ ✓ search_people: Found 5 people               │
│ ✓ search_journal_entries: Found 23 entries    │
└────────────────────────────────────────────────┘
```

### Phase 3: Final Response (White Box) - 4000-10000ms
```
┌────────────────────────────────────────────────┐
│ PHASE 3: RESPONSE                              │
│ ────────────────────────────────────────────── │
│ I've analyzed your conversations with people   │
│ in the construction industry and found some    │
│ interesting patterns:                          │
│                                                │
│ **Common Topics:**                             │
│ • Budget concerns came up in 80% of           │
│   conversations                                │
│ • Timeline pressure mentioned by all contacts │
│ • Material sourcing challenges (60%)          │
│                                                │
│ **Key People:**                                │
│ • John Smith - Foundation specialist█         │
│   [Continues streaming...]                     │
└────────────────────────────────────────────────┘
```

---

## The Magic

What makes this work:

1. **SSE Events** - Backend yields events as they happen
2. **Event Routing** - Frontend routes events to correct phase state
3. **queueMicrotask()** - Escapes React batching for immediate renders
4. **Conditional Rendering** - Each box only appears when phase has content
5. **State Management** - Separate states prevent mixing

Result: **True real-time streaming with visual phase separation!** 🎉
