#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Ensure typical user PATH is available (retrochaind, hermes, etc.)
source "$HOME/.bashrc" >/dev/null 2>&1 || true

BIN="$PROJECT_ROOT/dist/retrochain-node-manager"
PY="$PROJECT_ROOT/tools/gui_node_manager.py"

# Run from the repo root so relative paths (and the build/retrochaind default) resolve predictably.
cd "$PROJECT_ROOT"

# Prefer the locally built binary over any installed one.
export PATH="$PROJECT_ROOT/build:${GOBIN:-$HOME/go/bin}:$PATH"

# Optional: make the upgraded binary easy to reference/copy from logs/UI.
export RETROCHAIND_UPGRADED_BIN_DEFAULT="$PROJECT_ROOT/build/retrochaind-tokenfactory"

# Always prefer the Python entrypoint so the GUI reflects the latest repo code
# (the dist binary can easily get out of date).
if [[ "${USE_NODE_MANAGER_BIN:-}" == "1" && -x "$BIN" ]]; then
  exec "$BIN"
fi

exec /usr/bin/env python3 "$PY"

