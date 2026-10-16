#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HA_CONFIG:-${1:-}}"
if [[ -z "$TARGET" ]]; then
  echo 'Usage: HA_CONFIG=/path/to/ha/config bash ./install.sh' >&2
  exit 2
fi
TARGET="${TARGET%/}"
[[ -d "$TARGET" ]] || { echo "No config directory: $TARGET" >&2; exit 2; }
SRC="$ROOT/custom_components/air_quality_advisor"
DEST="$TARGET/custom_components/air_quality_advisor"
python3 -m compileall -q "$SRC"
mkdir -p "$TARGET/custom_components"
STAGE="$(mktemp -d "$TARGET/custom_components/.air_quality_advisor-stage-XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
cp -a "$SRC/." "$STAGE/"
find "$STAGE" -type d -name __pycache__ -prune -exec rm -rf '{}' +
if [[ -e "$DEST" ]]; then
  BACKUP="$TARGET/custom_components/.air_quality_advisor-backup-$(date +%Y%m%d-%H%M%S)"
  mv "$DEST" "$BACKUP"
  echo "Previous installation backed up at $BACKUP"
fi
mv "$STAGE" "$DEST"
trap - EXIT
printf 'INSTALLED=%s\nHOME_ASSISTANT_RESTART=REQUIRED_MANUALLY\nSSH_SESSION=UNCHANGED\n' "$DEST"
