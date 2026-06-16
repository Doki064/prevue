#!/usr/bin/env bash
# Mirror .github/workflows/ci.yml test-and-lint job locally before push/PR.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ACTIONLINT_VERSION="v1.7.12"
ZIZMOR_IMAGE="ghcr.io/zizmorcore/zizmor:v1.25.2"
WORKFLOW_FILES=(
  .github/workflows/ci.yml
  .github/workflows/review.yml
  .github/workflows/prevue-review.yml
  .github/workflows/prevue-command.yml
)

step() {
  printf '\n==> %s\n' "$1"
}

ensure_actionlint() {
  if command -v actionlint >/dev/null 2>&1; then
    printf '%s\n' actionlint
    return
  fi
  if ! command -v go >/dev/null 2>&1; then
    echo "actionlint not found and go is not installed." >&2
    echo "Install actionlint (https://github.com/rhysd/actionlint#installation) or go, then retry." >&2
    exit 1
  fi
  local candidate
  candidate="$(go env GOPATH)/bin/actionlint"
  if [[ -x "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return
  fi
  step "Installing actionlint ${ACTIONLINT_VERSION}"
  go install "github.com/rhysd/actionlint/cmd/actionlint@${ACTIONLINT_VERSION}"
  candidate="$(go env GOPATH)/bin/actionlint"
  if [[ ! -x "$candidate" ]]; then
    echo "actionlint install failed" >&2
    exit 1
  fi
  printf '%s\n' "$candidate"
}

run_zizmor() {
  if command -v zizmor >/dev/null 2>&1; then
    zizmor audit .github/workflows
    return
  fi
  if command -v docker >/dev/null 2>&1; then
    docker run --rm \
      -v "${ROOT}/.github/workflows:/workflows:ro" \
      "${ZIZMOR_IMAGE}" \
      audit /workflows
    return
  fi
  echo "zizmor not found. Install a binary or Docker, then retry:" >&2
  echo "  docker pull ${ZIZMOR_IMAGE}" >&2
  echo "  https://docs.zizmor.sh/installation/" >&2
  exit 1
}

step "uv sync --locked"
uv sync --locked

step "pytest (with coverage)"
uv run pytest --cov=prevue -q

step "ruff check"
uv run ruff check .

step "ruff format --check"
uv run ruff format --check .

step "actionlint"
ACTIONLINT="$(ensure_actionlint)"
"$ACTIONLINT" -color -shellcheck= -pyflakes= "${WORKFLOW_FILES[@]}"

step "zizmor"
run_zizmor

printf '\nCI local mirror passed.\n'
