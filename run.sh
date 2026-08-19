#!/usr/bin/env bash
# Starts the Blue Team Simulator dev server.
# Run from anywhere - always resolves paths relative to this script's location.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8731}"

exec .venv/bin/uvicorn app.main:app --reload --port "$PORT"
