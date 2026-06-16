# Simple Start Guide (Fixed the Restart Loop!)

## The Problem You Had

The server was restarting over and over because it was watching the `venv` folder for changes. I've fixed that! ✅

---

## How to Start Your Servers (New Way)

### Step 1: Stop the Looping Server

In the terminal that's looping, press:
```
CTRL + C
```

### Step 2: Start Backend (Fixed Version)

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
./start-backend.sh
```

**What you should see:**
```
Starting CAiS Command Center Backend...

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

Then it should just sit there quietly, waiting for requests. **No more looping!** ✅

**Keep this terminal open!**

---

### Step 3: Start Frontend (In a NEW Terminal)

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/frontend"
./start-frontend.sh
```

**What you should see:**
```
Starting CAiS Command Center Frontend...

▲ Next.js 15.x.x
- Local:        http://localhost:3000

Ready in X seconds
```

**Keep this terminal open too!**

---

### Step 4: Open Your App

Go to: **http://localhost:3000**

---

## Why Did This Happen?

The `--reload` flag tells the server to restart when files change (useful during development). But it was watching ALL files, including the Python packages in `venv/`, which caused it to restart constantly.

The fix: Tell it to ignore the `venv` folder with `--reload-exclude 'venv/*'`

---

## What You'll See Now

✅ **Backend terminal:** Shows logs when you use the app (API requests, database queries)
✅ **Frontend terminal:** Shows when pages are compiled
✅ **Browser:** Your working app!

Both should run quietly until you actually use the app.

---

## Stopping the Servers

When you're done:
1. Go to each terminal
2. Press `CTRL + C`
3. Type `exit` if you want to close the terminal

---

## Quick Reference

**Every time you want to start:**

Terminal 1:
```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
./start-backend.sh
```

Terminal 2:
```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/frontend"
./start-frontend.sh
```

Browser: http://localhost:3000

Done! 🎉
