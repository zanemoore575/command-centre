# Start Here - Simple Setup Guide 🚀

Follow these steps exactly. I'll guide you through each one!

## Step 1: Run the Setup Script

Open Terminal (the black window with white text) and copy-paste this:

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre"
./start.sh
```

**What this does:**
- Checks if PostgreSQL is installed and running
- Creates the database
- Installs all the code dependencies
- Sets everything up for you

**If you see any errors**, copy the error message and let me know!

---

## Step 2: Add Your API Key

You need an Anthropic API key to use Claude for entity extraction.

1. Go to: https://console.anthropic.com/settings/keys
2. Create a new API key (or copy your existing one)
3. Open this file: `/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend/.env`
4. Replace `your_anthropic_api_key_here` with your actual API key
5. Save the file

It should look like:
```
DATABASE_URL=postgresql://apple@localhost:5432/cais_command_center
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxx
ENVIRONMENT=development
```

---

## Step 3: Start the Backend Server

Open Terminal and run:

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
source venv/bin/activate
uvicorn app.main:app --reload
```

**What you should see:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Keep this terminal window open!** Don't close it.

To test it's working, open your browser and go to: http://localhost:8000/docs

You should see the API documentation page.

---

## Step 4: Start the Frontend Server

**Open a NEW terminal window** (don't close the first one!)

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/frontend"
npm run dev
```

**What you should see:**
```
▲ Next.js 15.x.x
- Local:        http://localhost:3000
Ready in X seconds
```

---

## Step 5: Open the App!

Open your web browser and go to:

**http://localhost:3000**

You should see the Command Centre homepage!

---

## Common Issues & Solutions

### "command not found: createdb"
**Solution:** PostgreSQL isn't installed. Install it:
```bash
brew install postgresql@14
brew services start postgresql@14
```

### "Database connection error"
**Solution:** PostgreSQL isn't running. Start it:
```bash
brew services start postgresql
```

### "Port 3000 is already in use"
**Solution:** Something else is using that port. Use a different port:
```bash
npm run dev -- -p 3001
```
Then go to http://localhost:3001

### "Port 8000 is already in use"
**Solution:** Use a different port for backend:
```bash
uvicorn app.main:app --reload --port 8001
```
Then update `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

---

## Stopping the Servers

When you want to stop:

1. Go to each terminal window
2. Press `CTRL + C`
3. Type `exit` to close the terminal

---

## Next Time You Want to Start

You only need to run Steps 3 and 4 again:

**Terminal 1 - Backend:**
```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
source venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/frontend"
npm run dev
```

---

## Need Help?

If you get stuck at any step:
1. Copy the exact error message
2. Tell me which step you're on
3. I'll help you fix it!

---

## Visual Guide

```
┌─────────────────────────────────────┐
│  Terminal 1: Backend                │
│  Port: 8000                         │
│  Command: uvicorn app.main:app      │
│  Status: ✓ Running                  │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  Database: PostgreSQL               │
│  Name: cais_command_center          │
│  Status: ✓ Running                  │
└─────────────────────────────────────┘
           ↑
┌─────────────────────────────────────┐
│  Terminal 2: Frontend               │
│  Port: 3000                         │
│  Command: npm run dev               │
│  Status: ✓ Running                  │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  Browser: http://localhost:3000     │
│  Your App: Command Centre      │
└─────────────────────────────────────┘
```

**All set!** Let's get your servers running! 🎉
