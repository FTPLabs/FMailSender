# Skill: GitHub Actions for Private Repo

  ## CRITICAL RULE: Repo must be PUBLIC during CI builds

  FTPLabs/FMailSender is a **private repo** but uses GitHub-hosted runners.
  GitHub Actions minutes are LIMITED for private repos (free tier: 2000 min/month, Windows = 2×).
  **Public repos get UNLIMITED free minutes.**

  ### Solution implemented in `release.yml`

  The workflow has two mandatory bookend steps:

  ```yaml
  - name: "Repo PUBLIC - build window open"
    shell: bash
    run: |
      curl -s -X PATCH \
        -H "Authorization: Bearer ${{ secrets.PAT_TOKEN }}" \
        -H "Content-Type: application/json" \
        "https://api.github.com/repos/FTPLabs/FMailSender" \
        -d '{"private":false}'

  - name: "Repo PRIVATE - build window closed"
    if: always()
    shell: bash
    run: |
      curl -s -X PATCH \
        -H "Authorization: Bearer ${{ secrets.PAT_TOKEN }}" \
        -d '{"private":true}' ...
  ```

  ### PAT_TOKEN requirements

  The `PAT_TOKEN` secret must be a GitHub Personal Access Token with:
  - **Scope**: `repo` (full repo access, needed to change visibility)
  - **Expiry**: set to "No expiration" or rotate before expiry
  - **Set via**: GitHub → FTPLabs/FMailSender → Settings → Secrets → Actions → PAT_TOKEN

  ### If builds start failing with 0 steps (no runner allocated)

  This means the build is running as a PRIVATE repo (minutes quota exhausted).

  **Fix (run once before triggering build):**
  ```bash
  curl -s -X PATCH \
    -H "Authorization: Bearer ghp_YOUR_PAT" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/FTPLabs/FMailSender" \
    -d '{\"private\":false}'
  ```

  Then trigger the workflow:
  ```
  GitHub → Actions → FMailSender Release → Run workflow
  ```

  The workflow will automatically make it private again at the end.

  ### Script: make-public-and-release.sh

  ```bash
  #!/bin/bash
  # Usage: PAT=ghp_... bash make-public-and-release.sh [version]
  # Makes repo public, triggers release, repo goes private after build.
  VERSION=${1:-"6.4.0"}
  PAT=${PAT:-$GITHUB_PAT}
  REPO="FTPLabs/FMailSender"

  echo "Making repo public..."
  curl -s -X PATCH \
    -H "Authorization: Bearer $PAT" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/$REPO" \
    -d '{"private":false}' | grep -o '"private":[a-z]*'

  echo "Triggering release v$VERSION..."
  curl -s -X POST \
    -H "Authorization: Bearer $PAT" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/$REPO/actions/workflows/302975497/dispatches" \
    -d "{\"ref\":\"main\",\"inputs\":{\"version\":\"$VERSION\"}}"

  echo "Done. Workflow started — repo will go private again after build."
  ```
  