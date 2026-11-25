#!/usr/bin/env bash
set -euo pipefail

echo "🔄 Syncing latest Production data into dev..."
git checkout dev
git pull --no-rebase origin main --no-edit || true
git push origin dev

echo "🚀 Promoting dev -> main (Production)..."
git checkout main
git pull origin main
git merge --no-ff dev -m "chore(release): promote dev sandbox to production"
git push origin main

git checkout dev
echo "✅ Promoted! Production (https://scottrepository.github.io/U13A-Tigers-2026-2027/) will update in ~1-2 minutes."
