# CAiS Command Center - Quick Start Guide

## Prerequisites

- PostgreSQL installed and running
- Node.js (v18+) installed
- Python 3.9+ installed
- Anthropic API key

## Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Run the setup script:
```bash
./setup.sh
```

Or manually:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create database
createdb cais_command_center

# Configure environment
# Edit .env file with your database URL and Anthropic API key

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

Backend will run at: http://localhost:8000
API docs at: http://localhost:8000/docs

## Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Configure environment:
```bash
cp .env.local.example .env.local
# Edit .env.local if needed (default: http://localhost:8000)
```

4. Start development server:
```bash
npm run dev
```

Frontend will run at: http://localhost:3000

## First Steps

1. Make sure both backend and frontend are running
2. Open http://localhost:3000 in your browser
3. Create your first journal entry
4. Watch the AI extract entities (people, commitments, pain points)
5. Explore the dashboard to see your journey timeline

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql://apple@localhost:5432/cais_command_center
ANTHROPIC_API_KEY=sk-ant-...
ENVIRONMENT=development
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Troubleshooting

### Database connection error
- Make sure PostgreSQL is running: `pg_ctl status`
- Check database exists: `psql -l | grep cais_command_center`
- Verify DATABASE_URL in backend/.env

### Port already in use
- Backend: Change port with `uvicorn app.main:app --reload --port 8001`
- Frontend: Change port with `npm run dev -- -p 3001`

### Migration errors
- Reset database: `alembic downgrade base && alembic upgrade head`
- Or drop and recreate: `dropdb cais_command_center && createdb cais_command_center && alembic upgrade head`

## Project Structure

```
CAiS Command Centre/
├── backend/          # FastAPI Python backend
│   ├── app/          # Application code
│   ├── alembic/      # Database migrations
│   └── tests/        # Tests
├── frontend/         # Next.js React frontend
│   └── src/
│       ├── app/      # Pages (App Router)
│       ├── components/  # React components
│       └── lib/      # Utilities
└── docs/            # Documentation
```

## Next Steps

After getting the app running:

1. Create some journal entries to populate data
2. Test entity extraction
3. Explore the people tracking feature
4. Check out the dashboard timeline
5. Start customizing for your needs!

## Getting Help

- Backend API docs: http://localhost:8000/docs
- Check logs in terminal for errors
- Review the implementation plan in `.claude/plans/` for architecture details
