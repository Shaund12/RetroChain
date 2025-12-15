#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Ensure typical user PATH is available (retrochaind, hermes, etc.)
source "$HOME/.bashrc" >/dev/null 2>&1 || true

BIN="$PROJECT_ROOT/dist/retrochain-node-manager"
PY="$PROJECT_ROOT/tools/gui_node_manager.py"

# Always prefer the Python entrypoint so the GUI reflects the latest repo code
# (the dist binary can easily get out of date).
if [[ "${USE_NODE_MANAGER_BIN:-}" == "1" && -x "$BIN" ]]; then
  exec "$BIN"
fi

exec /usr/bin/env python3 "$PY"
