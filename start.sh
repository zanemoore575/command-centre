#!/bin/bash

echo "================================================"
echo "   CAiS Command Center - Startup Script"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if PostgreSQL is installed
echo "Step 1: Checking PostgreSQL..."
if ! command -v psql &> /dev/null; then
    echo -e "${RED}✗ PostgreSQL is not installed${NC}"
    echo "Please install PostgreSQL first:"
    echo "  brew install postgresql@14"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL is installed${NC}"
echo ""

# Check if PostgreSQL is running
echo "Step 2: Checking if PostgreSQL is running..."
if ! pg_isready -q; then
    echo -e "${YELLOW}! PostgreSQL is not running. Starting it...${NC}"
    brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null
    sleep 3
    if ! pg_isready -q; then
        echo -e "${RED}✗ Failed to start PostgreSQL${NC}"
        echo "Please start it manually:"
        echo "  brew services start postgresql"
        exit 1
    fi
fi
echo -e "${GREEN}✓ PostgreSQL is running${NC}"
echo ""

# Check if database exists
echo "Step 3: Checking if database exists..."
if ! psql -lqt | cut -d \| -f 1 | grep -qw cais_command_center; then
    echo -e "${YELLOW}! Database doesn't exist. Creating it...${NC}"
    createdb cais_command_center 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Database created${NC}"
    else
        echo -e "${RED}✗ Failed to create database${NC}"
        echo "Please create it manually:"
        echo "  createdb cais_command_center"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Database exists${NC}"
fi
echo ""

# Setup backend
echo "Step 4: Setting up backend..."
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if [ ! -f "venv/bin/uvicorn" ]; then
    echo "Installing Python dependencies (this may take a minute)..."
    pip install --quiet --upgrade pip
    pip install --quiet fastapi uvicorn sqlalchemy psycopg2-binary alembic anthropic pydantic pydantic-settings python-dotenv
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi
echo ""

# Check .env file
echo "Step 5: Checking configuration..."
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}! No .env file found. Creating from template...${NC}"
    cat > .env << 'EOF'
DATABASE_URL=postgresql://$(whoami)@localhost:5432/cais_command_center
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ENVIRONMENT=development
EOF
    echo -e "${YELLOW}⚠ IMPORTANT: You need to add your Anthropic API key to backend/.env${NC}"
    echo ""
fi

# Run migrations
echo "Step 6: Running database migrations..."
alembic upgrade head 2>&1 | grep -v "INFO"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database migrations complete${NC}"
else
    echo -e "${RED}✗ Migration failed${NC}"
    exit 1
fi
echo ""

# Go back to root
cd ..

# Setup frontend
echo "Step 7: Setting up frontend..."
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies (this may take a minute)..."
    npm install --silent 2>&1 | tail -1
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi
echo ""

cd ..

echo "================================================"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo "================================================"
echo ""
echo "To start the servers, you'll need TWO terminal windows:"
echo ""
echo -e "${YELLOW}Terminal 1 - Backend:${NC}"
echo "  cd \"$PWD/backend\""
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo -e "${YELLOW}Terminal 2 - Frontend:${NC}"
echo "  cd \"$PWD/frontend\""
echo "  npm run dev"
echo ""
echo "Then open: http://localhost:3000"
echo ""
echo -e "${YELLOW}⚠ Don't forget to add your Anthropic API key to:${NC}"
echo "  backend/.env"
echo ""
