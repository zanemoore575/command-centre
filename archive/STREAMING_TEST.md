# Real-Time Streaming Test Guide

## Current Status
- ✅ Backend is streaming correctly (verified with curl)
- ✅ Frontend receives SSE events (visible in console logs)
- ❌ UI not updating in real-time (state changes not triggering renders)

## Test Steps

### 1. Open the Chat
- URL: http://localhost:3002/chat
- Open browser DevTools (F12)
- Go to Console tab

### 2. Ask a Question
Try: "Tell me about the people I've met recently"

### 3. Watch the Console Logs

You should see these logs streaming in REAL-TIME:

```
⚡ SSE Event: thinking - Analyzing your question and planning how to an...
💭 Thinking step collected: 1 steps
⚡ SSE Event: thinking - **
📝 Response chunk received, total length: 2
🎯 Setting streaming response: **
📊 Current state - thinking: 1 tools: 0 response: 2
🎨 RENDERING streaming UI - thinking: 1 tools: 0 response: 2
⚡ SSE Event: response_chunk - Based
📝 Response chunk received, total length: 7
...
```

### 4. What to Check

**In Console:**
- ⚡ SSE Event logs = Events arriving from backend
- 💭 Thinking step collected = State being updated
- 🎨 RENDERING streaming UI = Component re-rendering

**On Screen:**
- Should see thinking steps appear one by one
- Should see tool usage badges appear
- Should see response text stream word by word

### 5. Debug Info

If you see console logs but NO UI updates:

**Check:**
1. Are the 🎨 RENDERING logs appearing?
   - YES → UI is rendering but maybe too fast to see
   - NO → State updates not triggering renders

2. What do the RENDERING logs show?
   - `thinking: 0 tools: 0 response: 0` → State not being set
   - `thinking: 5 tools: 2 response: 100` → State is set, should be visible

3. Is there a React error in console?
   - Check for any red errors
   - Check for warnings about keys, etc.

## Backend Test (Direct)

To verify backend is streaming correctly:

```bash
curl -N -X POST "http://localhost:8000/api/chat/messages/agentic" \
  -F "message=What is 2+2?"
```

You should see events streaming in immediately:

```
data: {"type": "thinking", "content": "Analyzing your question..."}

data: {"type": "thinking", "content": "**"}

data: {"type": "thinking", "content": "2"}
```

## Expected Behavior

### Real-Time Streaming (Like Claude Code):
1. Click "Send"
2. IMMEDIATELY see: "Analyzing your question and planning..."
3. See thinking tokens appear: "**" "2" "+ 2"
4. See tool badges: "🔧 Using search_people..."
5. See response stream: "Based" "on" "your" "recent" ...
6. Everything happens LIVE, token by token

### Current Broken Behavior:
1. Click "Send"
2. See spinner + "Thinking..."
3. Wait 5-30 seconds
4. Everything appears AT ONCE
5. No streaming, just instant full result

## Next Debugging Steps

If UI still not updating after these code changes:

1. Check React DevTools Profiler
2. Check if NextJS is in production mode (should be dev)
3. Try disabling React.StrictMode if enabled
4. Check browser console for blocked renders
5. Try in incognito mode (disable extensions)
6. Check Network tab - are SSE events arriving?

## Files Modified

1. `frontend/src/app/chat/page.tsx`
   - Removed `flushSync()` (might have blocked renders)
   - Added extensive logging
   - Fixed render conditions
   - Added auto-scroll for streaming content

2. `backend/app/services/agentic_chat_service.py`
   - Changed `messages.create()` → `messages.stream()`
   - Real-time token streaming from Claude API
   - Immediate event yielding

## Success Criteria

✅ When you ask a question, you should see:
- Thinking steps appear one at a time (not all at once)
- Tool usage badges appear as tools are called
- Response text streams word by word
- Animated cursor shows active streaming
- Smooth, natural flow like Claude Code

The question is: Are you seeing the 🎨 RENDERING logs in console when you test?
