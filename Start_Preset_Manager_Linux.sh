#!/usr/bin/env bash
set -u
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
if command -v python3 >/dev/null 2>&1; then PYTHON=python3; elif command -v python >/dev/null 2>&1; then PYTHON=python; else echo "Python 3 fehlt / Python 3 is missing."; exit 1; fi
exec "$PYTHON" preset_manager.py "$SCRIPT_DIR/migration_catalog.json"
