#!/usr/bin/env sh
# Add HPMulti-Tool to the Linux application menu (current user only, no sudo).
set -e
cd "$(dirname "$0")"
APP_DIR="$(pwd)"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$ICON_DIR" "$HOME/.local/share/applications"
[ -x .venv/bin/python ] || ./start.sh --help >/dev/null
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "
from PySide6.QtGui import QGuiApplication
app = QGuiApplication([])
from hpmultitool.gui.icon import render_icon
render_icon(256).save('$ICON_DIR/hpmultitool.png')
"
cat > "$HOME/.local/share/applications/hpmultitool.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=HPMulti-Tool
Comment=Data acquisition for HP 34401A multimeters
Comment[de]=Messdatenerfassung für HP 34401A
Exec="$APP_DIR/start.sh"
Icon=hpmultitool
Terminal=false
Categories=Science;Electronics;Engineering;
EOF
echo "Menu entry created: HPMulti-Tool"
