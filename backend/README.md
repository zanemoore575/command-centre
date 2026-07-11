# Command Centre - Backend

FastAPI backend for the Command Centre personal AI system.

## Setup

1. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your database URL and Anthropic API key
```

4. Set up PostgreSQL database:
```bash
# Create database
createdb cais_command_center

# Run migrations
alembic upgrade head
```

5. Run the server:
```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

API documentation at http://localhost:8000/docs

## Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback:
```bash
alembic downgrade -1
```

## Testing

Run tests:
```bash
pytest
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── api/                 # API route handlers
│   ├── services/            # Business logic
│   └── utils/               # Utilities
├── alembic/                 # Database migrations
├── tests/                   # Tests
└── requirements.txt
```
