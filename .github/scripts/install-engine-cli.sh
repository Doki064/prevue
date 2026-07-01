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
    # D-12 / T-10-17: install Antigravity CLI (`agy`) via official curl script, with an
    # optional checksum gate mirroring the Cursor PREVUE_CURSOR_INSTALL_SHA256 pattern.
    # PREVUE_ANTIGRAVITY_INSTALL_SHA256: set to the sha256 of the install script to
    # enforce supply-chain integrity; leave unset to skip (development/trust-bootstrapping).
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
