# The Easiest Setup Guide (No Database Hassles!)

This guide uses SQLite instead of PostgreSQL - much simpler, no passwords, no setup!

## Step 1: Switch to SQLite

Open Terminal and run:

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre"
./use-sqlite.sh
```

## Step 2: Add Your API Key

1. Get your Anthropic API key: https://console.anthropic.com/settings/keys
2. Open this file: `/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend/.env`
3. Replace `your_anthropic_api_key_here` with your key
4. Save

## Step 3: Set Up Backend

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

## Step 4: Start Backend Server

```bash
uvicorn app.main:app --reload
```

**Keep this terminal open!**

Test it: Open http://localhost:8000/docs in your browser

## Step 5: Set Up Frontend (New Terminal)

Open a NEW terminal window:

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/frontend"
npm install
npm run dev
```

## Step 6: Open Your App!

Go to: **http://localhost:3000**

---

## That's It!

You should now see your Command Centre running! 🎉

The database is stored as a file: `backend/cais_command_center.db`

---

## Starting It Later

When you want to use it again:

**Terminal 1:**
```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
source venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2:**
```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/frontend"
npm run dev
```

**Browser:** http://localhost:3000

Done! ✨
