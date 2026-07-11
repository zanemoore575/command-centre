# Command Centre - Complete Setup Tutorial

## What We're Going to Do

1. Set up PostgreSQL (your database)
2. Install backend dependencies (Python stuff)
3. Install frontend dependencies (JavaScript stuff)
4. Start both servers
5. Open the app in your browser!

Don't worry - I'll explain everything step by step. 🎯

---

## Prerequisites Check

Let's make sure you have the basics installed.

### Check if you have Homebrew

Open Terminal and type:
```bash
brew --version
```

**If you see a version number:** ✅ You're good!

**If you see "command not found":** Install Homebrew first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

## Part 1: Set Up PostgreSQL Database

### Step 1.1: Install PostgreSQL

```bash
brew install postgresql@14
```

Wait for this to finish (might take a few minutes).

### Step 1.2: Start PostgreSQL

```bash
brew services start postgresql@14
```

You should see: `Successfully started postgresql@14`

### Step 1.3: Create the Database

Now we'll create the database. Since you have password authentication set up, let's do it through the PostgreSQL app:

```bash
psql postgres
```

If it asks for a password, just press Enter (leave it blank).

**If that doesn't work**, try:
```bash
psql -d postgres
```

Once you're in PostgreSQL (you'll see `postgres=#`), type:

```sql
CREATE DATABASE cais_command_center;
```

Then type:
```sql
\q
```

(This quits PostgreSQL)

**Alternatively**, if the above doesn't work, let's use SQLite instead (simpler, no password needed):

Just skip to Part 2 and I'll help you configure SQLite instead.

---

## Part 2: Set Up the Backend (Python/FastAPI)

### Step 2.1: Navigate to Backend Folder

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
```

### Step 2.2: Activate Virtual Environment

```bash
source venv/bin/activate
```

You should see `(venv)` appear at the start of your command line.

### Step 2.3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install all the Python packages needed. Wait for it to finish.

### Step 2.4: Configure Your Settings

Open this file in a text editor:
```
/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend/.env
```

It should look like this:
```
DATABASE_URL=postgresql://apple@localhost:5432/cais_command_center
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ENVIRONMENT=development
```

**You need to:**
1. Get your Anthropic API key from https://console.anthropic.com/settings/keys
2. Replace `your_anthropic_api_key_here` with your actual key
3. Save the file

**If PostgreSQL isn't working**, change the DATABASE_URL to:
```
DATABASE_URL=sqlite:///./cais_command_center.db
```

This will use SQLite instead (much simpler, stored as a file).

### Step 2.5: Set Up the Database

```bash
alembic upgrade head
```

You should see some output about creating tables. That's good!

### Step 2.6: Start the Backend Server

```bash
uvicorn app.main:app --reload
```

**You should see:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**✅ SUCCESS!** Your backend is running!

**Test it:** Open your browser and go to http://localhost:8000/docs

You should see the API documentation page.

**Keep this terminal window open!**

---

## Part 3: Set Up the Frontend (Next.js/React)

### Step 3.1: Open a NEW Terminal Window

Don't close the backend terminal! Open a brand new one.

### Step 3.2: Navigate to Frontend Folder

```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/frontend"
```

### Step 3.3: Install Dependencies

```bash
npm install
```

This might take a minute or two. It's downloading all the JavaScript packages.

### Step 3.4: Start the Frontend Server

```bash
npm run dev
```

**You should see:**
```
▲ Next.js 15.x.x
- Local:        http://localhost:3000
Ready in X seconds
```

**✅ SUCCESS!** Your frontend is running!

---

## Part 4: Open Your App!

Open your web browser and go to:

**http://localhost:3000**

You should see the Command Centre homepage! 🎉

---

## Quick Reference - Starting the Servers

After the initial setup, here's all you need to do each time:

### Terminal 1 - Backend:
```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/backend"
source venv/bin/activate
uvicorn app.main:app --reload
```

### Terminal 2 - Frontend:
```bash
cd "/Users/apple/Desktop/Claude_code/CAiS Command Centre/frontend"
npm run dev
```

Then open: **http://localhost:3000**

---

## Troubleshooting

### "ModuleNotFoundError" when starting backend
**Solution:** Make sure you activated the virtual environment:
```bash
source venv/bin/activate
```

### "alembic: command not found"
**Solution:** Install dependencies again:
```bash
pip install -r requirements.txt
```

### "npm: command not found"
**Solution:** Install Node.js:
```bash
brew install node
```

### PostgreSQL password issues
**Solution:** Use SQLite instead. Edit `backend/.env`:
```
DATABASE_URL=sqlite:///./cais_command_center.db
```

Then run the migration again:
```bash
alembic upgrade head
```

### Port already in use errors

**For backend (port 8000):**
```bash
uvicorn app.main:app --reload --port 8001
```
Then update `frontend/.env.local` to:
```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

**For frontend (port 3000):**
```bash
npm run dev -- -p 3001
```
Then go to http://localhost:3001

---

## What's Running?

When everything is working, you have:

1. **Terminal 1:** Backend server (Python/FastAPI) on port 8000
2. **Terminal 2:** Frontend server (Next.js/React) on port 3000
3. **Database:** PostgreSQL (or SQLite file)
4. **Browser:** Your app at http://localhost:3000

---

## Need Help?

If you get stuck:

1. **Check which step failed** - Look at the error message
2. **Copy the exact error** - Don't paraphrase
3. **Tell me:**
   - Which step you're on
   - The exact command you ran
   - The exact error message
   - What you see in the terminal

I'll help you fix it! 🚀

---

## Next Steps

Once everything is running, you're ready to build the journal entry system! That's Phase 2 of the project. But first, let's make sure Phase 1 (the foundation) is solid.
