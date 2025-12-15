#!/usr/bin/env bash
set -euo pipefail

# Build a desktop-friendly binary using PyInstaller.
# Requirements: pip install pyinstaller

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$PROJECT_ROOT"

pyinstaller --name retrochain-node-manager \
  --windowed \
  --onefile \
  --add-data "tools/gui_node_manager.py:." \
  tools/gui_node_manager.py

echo "Build complete: dist/retrochain-node-manager"
