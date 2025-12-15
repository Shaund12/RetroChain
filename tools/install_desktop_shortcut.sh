#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Retrochain Node Manager"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LAUNCHER_PATH="${PROJECT_ROOT}/tools/launch_node_manager.sh"
DESKTOP_FILE="$HOME/.local/share/applications/retrochain-node-manager.desktop"
ICON_NAME="utilities-terminal"

if [[ ! -x "$LAUNCHER_PATH" ]]; then
  echo "Launcher not found or not executable: $LAUNCHER_PATH" >&2
  echo "Fix: chmod +x $LAUNCHER_PATH" >&2
  exit 1
fi

mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Start/stop Retrochain node, Hermes, and Modules commands
Exec=$LAUNCHER_PATH
Icon=$ICON_NAME
Terminal=false
Categories=Utility;
EOF

chmod +x "$DESKTOP_FILE"
update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true

echo "Desktop launcher created: $DESKTOP_FILE"
echo "You may need to relog or refresh your application menu."
