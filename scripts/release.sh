#!/bin/bash
  # FMailSender Release Helper
  # Usage: PAT=ghp_... bash scripts/release.sh [version]
  # Makes repo public, triggers GitHub Actions release, repo returns to private after build.

  set -e

  VERSION="${1:-6.4.0}"
  PAT="${PAT:-${GITHUB_PAT:-}}"
  REPO="FTPLabs/FMailSender"
  WORKFLOW_ID="302975497"

  if [ -z "$PAT" ]; then
    echo "ERROR: Set PAT environment variable to your GitHub PAT (repo scope)"
    echo "Usage: PAT=ghp_... bash scripts/release.sh 6.4.0"
    exit 1
  fi

  echo "=== FMailSender Release Helper ==="
  echo "Version: v$VERSION"
  echo "Repo: $REPO"
  echo ""

  echo "[1/3] Making repo PUBLIC (required for free Actions minutes)..."
  RESULT=$(curl -s -X PATCH \
    -H "Authorization: Bearer $PAT" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/$REPO" \
    -d '{"private":false}')
  VISIBILITY=$(echo "$RESULT" | grep -o '"private":[a-z]*' || echo "unknown")
  echo "   Visibility: $VISIBILITY"

  echo "[2/3] Triggering GitHub Actions release workflow for v$VERSION..."
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Authorization: Bearer $PAT" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/$REPO/actions/workflows/$WORKFLOW_ID/dispatches" \
    -d "{\"ref\":\"main\",\"inputs\":{\"version\":\"$VERSION\"}}")

  if [ "$HTTP" = "204" ]; then
    echo "   Workflow started ✓"
  else
    echo "   WARNING: Dispatch returned HTTP $HTTP"
  fi

  echo "[3/3] Waiting 10s for workflow to appear..."
  sleep 10

  echo ""
  echo "=== Status ==="
  RUN=$(curl -s \
    -H "Authorization: Bearer $PAT" \
    "https://api.github.com/repos/$REPO/actions/runs?per_page=1")
  STATUS=$(echo "$RUN" | grep -o '"status":"[^"]*"' | head -1)
  echo "Latest run: $STATUS"
  echo ""
  echo "Monitor at: https://github.com/$REPO/actions"
  echo "Repo goes PRIVATE automatically when workflow finishes (Repo PRIVATE step)."
  