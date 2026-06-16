#!/bin/bash

echo "================================================"
echo "   Switching to SQLite Database"
echo "================================================"
echo ""
echo "This script will configure your backend to use"
echo "SQLite instead of PostgreSQL (much simpler!)"
echo ""

# Update .env file
cd backend

if [ -f ".env" ]; then
    # Backup existing .env
    cp .env .env.backup
    echo "✓ Backed up existing .env to .env.backup"
fi

# Create new .env with SQLite
cat > .env << 'EOF'
DATABASE_URL=sqlite:///./cais_command_center.db
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ENVIRONMENT=development
EOF

echo "✓ Updated .env to use SQLite"
echo ""
echo "IMPORTANT: You still need to add your Anthropic API key!"
echo "Edit this file: backend/.env"
echo ""
echo "Now run the database migration:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  alembic upgrade head"
echo ""
echo "Then start the server:"
echo "  uvicorn app.main:app --reload"
echo ""
