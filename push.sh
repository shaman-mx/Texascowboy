#!/usr/bin/env bash
set -euo pipefail

MSG="${1:-Update}"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"

git add .
git commit -m "$MSG" || true
git fetch origin
git rebase "origin/$BRANCH"
git push --force-with-lease origin "$BRANCH"