#!/bin/bash

# Инициализация review-questions/status.json из config/generation-status.json.
# Уже существующие записи сохраняются (idempotent), новые главы добавляются как pending.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATUS_FILE="$SCRIPT_DIR/status.json"

CHAPTERS=$(ls "$PROJECT_ROOT/chapters" | sort)

EXISTING='{"chapters":{}}'
if [ -f "$STATUS_FILE" ]; then
    EXISTING=$(cat "$STATUS_FILE")
fi

echo "$CHAPTERS" | jq -R . | jq -s --argjson existing "$EXISTING" '
  reduce .[] as $dir ({"chapters": {}};
    .chapters[$dir] = ($existing.chapters[$dir] // {"status": "pending"}))
' > "$STATUS_FILE"

TOTAL=$(jq '.chapters | length' "$STATUS_FILE")
PENDING=$(jq '[.chapters[] | select(.status == "pending")] | length' "$STATUS_FILE")
echo "status.json: $TOTAL глав, $PENDING pending"
