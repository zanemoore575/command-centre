# How to Restart Backend After Updates

## Quick Steps

1. **Stop the current backend server**
   - Go to the terminal running the backend
   - Press `CTRL + C`

2. **Restart with the new code**
   ```bash
   cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
   source venv/bin/activate
   ./start-backend.sh
   ```

3. **Verify it's running**
   - You should see: `INFO: Uvicorn running on http://127.0.0.1:8000`
   - No errors should appear

## What Just Got Fixed

✅ **Upgraded Anthropic SDK** from 0.39.0 to 0.76.0 (latest version)
✅ **Updated model** to use `claude-sonnet-4-5-20250929` (Claude Sonnet 4.5 - best balance of intelligence, speed, and cost)
✅ **Added error handling** in Claude client initialization

## After Restarting

Your backend should now:
- Start without the `proxies` error
- Successfully call Claude API for entity extraction
- Process journal entries in the background

## Test It

1. Go to http://localhost:3000/journal/new
2. Create an entry with people, commitments, and pain points
3. View the entry detail page
4. Wait 3-5 seconds and refresh
5. See the AI-extracted entities! 🤖

---

**If you still see errors**, copy the exact error message from the backend terminal and let me know!
