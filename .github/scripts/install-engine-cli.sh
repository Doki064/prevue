#!/usr/bin/env bash
set -euo pipefail

: "${PREVUE_ENGINE:=copilot-cli}"

case "$PREVUE_ENGINE" in
  copilot-cli)
    npm install -g @github/copilot@1.0.67
    command -v copilot
    ;;
  claude-code-cli)
    npm install -g @anthropic-ai/claude-code@2.1.177
    command -v claude
    ;;
  cursor-cli)
    installer="${RUNNER_TEMP}/cursor-install.sh"
    curl -fsS https://cursor.com/install -o "$installer"
    if [ -n "${PREVUE_CURSOR_INSTALL_SHA256:-}" ]; then
      echo "${PREVUE_CURSOR_INSTALL_SHA256}  ${installer}" | sha256sum -c -
    fi
    bash "$installer"
    command -v cursor-agent
    ;;
  antigravity-cli)
    # Optional PREVUE_ANTIGRAVITY_INSTALL_SHA256 checksum gate (mirrors Cursor pattern).
    installer="${RUNNER_TEMP}/antigravity-install.sh"
    curl -fsS https://antigravity.google/cli/install.sh -o "$installer"
    if [ -n "${PREVUE_ANTIGRAVITY_INSTALL_SHA256:-}" ]; then
      echo "${PREVUE_ANTIGRAVITY_INSTALL_SHA256}  ${installer}" | sha256sum -c -
    fi
    bash "$installer"
    command -v agy
    ;;
  *)
    echo "Unsupported engine: $PREVUE_ENGINE" >&2
    exit 1
    ;;
esac
