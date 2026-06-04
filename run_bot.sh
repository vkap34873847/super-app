#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/trading_bot" || { echo "trading_bot/ not found"; exit 1; }
echo "Starting Stock Bot (Market Scanner + Papa Approach)..."
echo "Open http://127.0.0.1:5000 in your browser"
exec "$DIR/venv/bin/python" app.py
