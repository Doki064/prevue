#!/usr/bin/env bash
# Switch uat/active/ to a named scenario for Phase 3 live UAT.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCENARIOS="$ROOT/uat/scenarios"
ACTIVE="$ROOT/uat/active"

usage() {
  echo "Usage: $0 <scenario-id>" >&2
  echo "Available:" >&2
  ls -1 "$SCENARIOS" 2>/dev/null | sed 's/^/  /' >&2
  exit 1
}

[[ $# -eq 1 ]] || usage
SCENARIO="$1"
SRC="$SCENARIOS/$SCENARIO"
[[ -d "$SRC" ]] || { echo "Unknown scenario: $SCENARIO" >&2; usage; }

rm -rf "$ACTIVE"
mkdir -p "$ACTIVE"
cp -a "$SRC/." "$ACTIVE/"
echo "$SCENARIO" > "$ROOT/uat/ACTIVE"
echo "Active scenario: $SCENARIO ($(find "$ACTIVE" -type f | wc -l) file(s))"
echo "Stage only: git add uat/active uat/ACTIVE"
