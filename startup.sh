#!/bin/bash

echo "🚀 Starting Anantam AI ERP..."

cd /home/anantam/anantam-erp

echo "🔹 Activating virtual environment..."

# ✅ Correct venv name
source erp-env/bin/activate

# Check if activation worked
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Virtual environment activation failed"
    exit 1
fi

echo "✅ Virtual environment activated: $VIRTUAL_ENV"

echo "🔹 Applying migrations..."
python manage.py migrate

echo "🔹 Cleaning port 8000..."
fuser -k 8000/tcp 2>/dev/null

echo "🔹 Starting Django server..."
python manage.py runserver 0.0.0.0:8000 &

sleep 3

echo "🔹 Starting ngrok..."
ngrok http 8000
