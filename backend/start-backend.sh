#!/bin/bash

echo "Starting CAiS Command Center Backend..."
echo ""

# Activate virtual environment
source venv/bin/activate

# Start server with proper reload settings
uvicorn app.main:app \
  --reload \
  --reload-exclude 'venv/*' \
  --reload-exclude '*.pyc' \
  --reload-exclude '__pycache__/*' \
  --host 0.0.0.0 \
  --port 8000

# The --reload-exclude prevents watching venv files
# --host 0.0.0.0 allows access from other devices (optional)
# --port 8000 is the default port
