# Test Guide: Phase Separation Streaming

## Quick Start

### 1. Open the Chat
```
URL: http://localhost:3002/chat
```

### 2. Open Browser Console (F12)
- Go to Console tab
- Watch for phase-specific logs

### 3. Ask a Complex Question

Try one of these:
```
"Who have I talked to about construction?"
"What patterns do you see in my recent conversations?"
"Show me all high-priority tasks and who they're for"
```

## What You Should See

### On Screen - Three Separate Boxes

#### Box 1: Gray Background (Planning Phase)
```
┌─────────────────────────────────────────────┐
│ PHASE 1: PLANNING                           │
│ ───────────────────────────────────────────│
│ 💭 Analyzing your question and planning    │
│    how to answer it...                      │
└─────────────────────────────────────────────┘
```
- Appears FIRST
- Gray background with gray left border
- Italic text with 💭 emoji

#### Box 2: Blue Background (Tool Execution Phase)
```
┌─────────────────────────────────────────────┐
│ PHASE 2: TOOL EXECUTION                     │
│ ───────────────────────────────────────────│
│ 🔧 Using search_people...                   │
│ 🔧 Using search_journal_entries...          │
│                                              │
│ ✓ search_people: Found 3 people            │
│ ✓ search_journal_entries: Found 12 entries│
└─────────────────────────────────────────────┘
```
- Appears SECOND (when tools are needed)
- Blue background with blue left border
- Tool badges in monospace font
- Green checkmarks for results

#### Box 3: White Background (Final Response Phase)
```
┌─────────────────────────────────────────────┐
│ PHASE 3: RESPONSE                           │
│ ───────────────────────────────────────────│
│ Based on your journal entries, you've      │
│ talked to several people about              │
│ construction:                                │
│                                              │
│ 1. **John Smith** - Discussed...█          │
│    [Streams in word by word]                │
└─────────────────────────────────────────────┘
```
- Appears THIRD
- Clean white background
- Markdown formatted prose
- Animated cursor (█) shows active typing

### In Console - Real-Time Logs

```javascript
⚡ SSE Event: thinking - Analyzing your question...
💭 Phase 1 Thinking: 1 steps

⚡ SSE Event: tool_use - Using search_people...
🔧 Phase 2 Tool: 1 tools

⚡ SSE Event: thinking - ✓ search_people: Found 3 people
✅ Phase 2 Results: 1 results

⚡ SSE Event: tool_use - Using search_journal_entries...
🔧 Phase 2 Tool: 2 tools

⚡ SSE Event: thinking - ✓ search_journal_entries: Found 12 entries
✅ Phase 2 Results: 2 results

⚡ SSE Event: response_chunk - Based
📝 Phase 3 Response chunk, total length: 5

⚡ SSE Event: response_chunk -  on
📝 Phase 3 Response chunk, total length: 8

⚡ SSE Event: response_chunk -  your
📝 Phase 3 Response chunk, total length: 13
...
```

## Success Checklist

### Visual Separation ✅
- [ ] Three distinct boxes appear on screen
- [ ] Each box has different background color (gray, blue, white)
- [ ] Each box has a phase label (Phase 1, Phase 2, Phase 3)
- [ ] Boxes appear sequentially, not all at once

### Phase 1: Planning ✅
- [ ] Gray box appears first
- [ ] Shows "Analyzing your question..." text
- [ ] Appears immediately after clicking Send

### Phase 2: Tool Execution ✅
- [ ] Blue box appears second (only if tools needed)
- [ ] Shows tool badges (🔧 Using...)
- [ ] Shows tool results (✓ Found X results)
- [ ] Tool badges and results are visually distinct

### Phase 3: Final Response ✅
- [ ] White box appears third
- [ ] Response text streams in word by word
- [ ] Animated cursor shows active typing
- [ ] Markdown formatting works (bold, lists, etc.)

### Real-Time Streaming ✅
- [ ] No delay - boxes appear immediately
- [ ] Each event updates UI in real-time
- [ ] Console logs show events arriving
- [ ] Text streams smoothly, not all at once

### After Completion ✅
- [ ] Three boxes disappear
- [ ] Single saved message appears
- [ ] Saved message shows condensed thinking/tools
- [ ] Ready for next question

## Common Issues

### Issue 1: All Content in One Box
**Problem**: Everything appears in a single message, mixed together
**Solution**: Check console - are phase-specific logs appearing?
- Look for "💭 Phase 1 Thinking"
- Look for "🔧 Phase 2 Tool"
- Look for "📝 Phase 3 Response chunk"

If not seeing phase logs, the event routing isn't working.

### Issue 2: No Real-Time Updates
**Problem**: Boxes appear all at once after waiting
**Solution**: Check if backend is streaming properly
```bash
curl -N -X POST "http://localhost:8000/api/chat/messages/agentic" \
  -F "message=What is 2+2?"
```
Should see events streaming immediately, not all at once.

### Issue 3: Only Phase 1 and 3, No Phase 2
**Problem**: Gray box → White box, but no blue box
**Solution**: This is normal for simple questions that don't need tools!
- Try a question that requires searching: "Who have I talked to about X?"
- Simple questions (like "Hello") don't need tools, so phase 2 is skipped

### Issue 4: Boxes Appear Too Fast
**Problem**: All three boxes appear instantly, can't see streaming
**Solution**:
1. Check console logs - are events streaming or coming all at once?
2. Try a more complex question that requires multiple tools
3. Check network tab - are SSE events arriving in real-time?

## Advanced Testing

### Test Different Question Types

#### 1. Simple Question (No Tools)
```
"Hello"
```
**Expected**: Phase 1 → Phase 3 (no phase 2, no tools needed)

#### 2. Search Question (Uses Tools)
```
"Who have I talked to about construction?"
```
**Expected**: Phase 1 → Phase 2 (tools) → Phase 3

#### 3. Complex Multi-Tool Question
```
"What patterns do you see in my conversations with people about construction?"
```
**Expected**: Phase 1 → Phase 2 (multiple tools) → Phase 3

#### 4. File Upload Question
```
"Analyze this invoice" + upload image
```
**Expected**: Phase 1 (file processing) → Phase 2 (optional) → Phase 3

### Monitor Network Tab

1. Open DevTools → Network tab
2. Filter by "agentic"
3. Click on the request
4. Look at Response tab
5. Should see events streaming in real-time

```
data: {"type":"thinking","content":"Analyzing..."}

data: {"type":"tool_use","tool_name":"search_people","content":"Using search_people..."}

data: {"type":"thinking","content":"✓ search_people: Found 3 people"}

data: {"type":"response_chunk","content":"Based"}
```

## Debugging

### Enable Verbose Logging

The code already has console logs built in. Watch for:

**Event Reception**:
```
⚡ SSE Event: thinking - ...
⚡ SSE Event: tool_use - ...
⚡ SSE Event: response_chunk - ...
```

**Phase Updates**:
```
💭 Phase 1 Thinking: X steps
🔧 Phase 2 Tool: X tools
✅ Phase 2 Results: X results
📝 Phase 3 Response chunk, total length: X
```

**Final Statistics**:
```
📊 Final phase 1 thinking: X
📊 Final phase 2 tools: X
📊 Final phase 2 results: X
📊 Final phase 3 response length: X
```

### Check State Updates

Add this to your browser console while testing:
```javascript
// Watch for React re-renders
const observer = new PerformanceObserver((list) => {
  list.getEntries().forEach((entry) => {
    console.log('⚡ Render:', entry.name, entry.duration);
  });
});
observer.observe({ entryTypes: ['measure'] });
```

## Expected Timeline

For a typical complex question:

```
00:00 - User clicks "Send"
00:00 - Gray box appears: "Starting..."
00:01 - Gray box updates: "Analyzing your question..."
00:02 - Blue box appears: "🔧 Using search_people..."
00:03 - Blue box updates: "✓ search_people: Found 3 people"
00:04 - Blue box updates: "🔧 Using search_journal_entries..."
00:05 - Blue box updates: "✓ search_journal_entries: Found 12 entries"
00:06 - White box appears: "Based" [cursor blinking]
00:07 - White box updates: "Based on your" [cursor blinking]
00:08 - White box updates: "Based on your journal entries..." [streaming]
... continues streaming ...
00:15 - All three boxes disappear
00:15 - Single saved message appears with full content
```

## Success!

If you see:
1. ✅ Three distinct boxes with different colors
2. ✅ Boxes appear sequentially (gray → blue → white)
3. ✅ Each phase streams content in real-time
4. ✅ Console logs show phase-specific updates
5. ✅ Final response streams word-by-word

**Then phase separation is working perfectly!** 🎉

## Still Not Working?

1. **Restart both servers**
   ```bash
   # Backend
   cd backend
   pkill -f uvicorn
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

   # Frontend (in new terminal)
   cd frontend
   npm run dev
   ```

2. **Clear browser cache**
   - Hard reload: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
   - Or use incognito mode

3. **Check both servers are running**
   ```bash
   lsof -ti:8000  # Backend
   lsof -ti:3002  # Frontend
   ```

4. **Check for errors**
   - Backend: Look at uvicorn terminal
   - Frontend: Look at npm terminal
   - Browser: Look at console for red errors
