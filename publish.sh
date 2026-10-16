#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
OWNER="${GITHUB_OWNER:-Chreece}"
NAME="HA-Air-Quality-Advisor"
REPO="$OWNER/$NAME"
command -v git >/dev/null || { echo 'git is required' >&2; exit 2; }
command -v gh >/dev/null || { echo 'GitHub CLI (gh) is required' >&2; exit 2; }
gh auth status >/dev/null || { echo 'Run gh auth login before publishing.' >&2; exit 2; }
python3 -m compileall -q custom_components
git init -b main >/dev/null 2>&1 || true
# Deliberately never force any existing git branches, remotes, or repositories.
CURRENT="$(git remote get-url origin 2>/dev/null || true)"
if [[ -n "$CURRENT" && "$CURRENT" != "https://github.com/$REPO.git" && "$CURRENT" != "git@github.com:$REPO.git" ]]; then
    echo "Refusing to change existing origin: $CURRENT" >&2
    exit 2
fi
if ! gh repo view "$REPO" >/dev/null 2>&1; then
    gh repo create "$REPO" --public --description 'Room-aware window ventilation recommendations using indoor/outdoor air quality, weather, alerts and optional TTS.'
fi
if [[ -z "$CURRENT" ]]; then
    git remote add origin "https://github.com/$REPO.git"
fi
if [[ "$(git branch --show-current)" != 'main' ]]; then
    echo 'Publish from main branch only; refusing to change existing branches.' >&2
    exit 2
fi
git add .
if ! git diff --cached --quiet; then
    git commit -m 'feat: add HACS-ready Air Quality Advisor v0.1.0'
fi
git fetch origin main
if ! git merge-base --is-ancestor origin/main HEAD; then
    echo "Remote main contains commits not present locally; refusing non-fast-forward push." >&2
    echo "Use an existing clone or pull/rebase after reviewing remote changes." >&2
    exit 2
fi
git push -u origin main
# Repository metadata is optional for custom HACS, useful for discovery.
gh repo edit "$REPO" --description 'Room-aware air quality and window ventilation advisor for Home Assistant, with weather alerts and optional announcements.' --enable-issues || true
gh repo edit "$REPO" --add-topic 'home-assistant,hacs,custom-integration,air-quality,ventilation,tts,notifications,weather' || true
printf 'REPOSITORY=https://github.com/%s\nGITHUB_ACTIONS=MANUAL_ONLY\nSSH_SESSION=UNCHANGED\n' "$REPO"
