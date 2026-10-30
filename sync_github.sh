#!/bin/bash
# 2ndbrainforsocialscience GitHub Auto-Sync Script
# Usage: ./sync_github.sh ["Commit message optional"]

set -e

REPO_DIR="/Users/gimjunseong/Downloads/02_인공지능·컴퓨터과학/05_오픈소스_소프트웨어프로젝트/2ndbrainforsocialscience-main"
cd "$REPO_DIR"

echo "=================================================="
echo "🛠️ 2ndbrainforsocialscience GitHub Synchronization"
echo "=================================================="
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"

# 1. Fetch latest changes
git fetch origin main

# 2. Add all changes
git add -A

# 3. Check if there are changes to commit
if git diff-index --quiet HEAD --; then
    echo "✔ No uncommitted local changes."
else
    MSG="${1:-auto-sync: Update 2ndbrain tools & pipeline ($(date '+%Y-%m-%d %H:%M:%S'))}"
    git commit -m "$MSG"
    echo "✔ Committed local changes: $MSG"
fi

# 4. Pull and rebase to avoid merge conflicts
git pull --rebase origin main

# 5. Push to GitHub
git push origin main

echo "=================================================="
echo "🚀 Successfully synced with GitHub (origin/main)!"
echo "   Remote: https://github.com/duomo77/2ndbrainforsocialscience.git"
echo "=================================================="
