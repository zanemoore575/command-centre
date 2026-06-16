#!/bin/bash

echo "CAiS Command Center - Backend Setup"
echo "===================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if database exists
echo ""
echo "Checking PostgreSQL database..."
DB_EXISTS=$(psql -lqt | cut -d \| -f 1 | grep -w cais_command_center | wc -l)

if [ $DB_EXISTS -eq 0 ]; then
    echo "Creating database 'cais_command_center'..."
    createdb cais_command_center
    if [ $? -eq 0 ]; then
        echo "✓ Database created successfully"
    else
        echo "✗ Failed to create database. Please create it manually:"
        echo "  createdb cais_command_center"
        exit 1
    fi
else
    echo "✓ Database already exists"
fi

# Run migrations
echo ""
echo "Running database migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✓ Migrations completed successfully"
else
    echo "✗ Migrations failed. Check the error above."
    exit 1
fi

echo ""
echo "===================================="
echo "Setup complete!"
echo ""
echo "To start the server:"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
