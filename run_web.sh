#!/bin/bash
cd "$(dirname "$0")"

# Check for venv
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Install Flask if missing
pip install flask --quiet

echo ""
echo "Starting Inventra Web..."
python web_server.py
