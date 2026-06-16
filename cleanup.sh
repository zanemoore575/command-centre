#!/bin/bash

echo "CAiS Command Center - Cleanup Script"
echo "====================================="
echo ""

# Clean Next.js cache
echo "Cleaning Next.js cache..."
cd frontend
rm -rf .next
rm -rf node_modules/.cache
echo "✓ Next.js cache cleared"

# Clean Python cache
echo "Cleaning Python cache..."
cd ../backend
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo "✓ Python cache cleared"

cd ..

echo ""
echo "Cleanup complete!"
echo ""
echo "Now restart your frontend server:"
echo "  cd frontend"
echo "  npm run dev"
