#!/usr/bin/env bash
set -euo pipefail

git checkout dev
echo "🔄 Pulling latest game/GameSheet data from main into dev..."
git pull origin main --no-edit || true

echo "🧪 Starting local Sandbox at http://localhost:8000 (Ctrl+C to stop)..."
python3 -m http.server 8000
