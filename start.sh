#!/usr/bin/env sh
# Start HPMulti-Tool on Linux. Creates the virtual environment on first run.
#   ./start.sh              real instruments
#   ./start.sh --simulate   two simulated instruments
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    echo "First start: setting up the Python environment …"
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip >/dev/null
    .venv/bin/pip install -r requirements.txt
fi
# Qt >= 6.5 needs libxcb-cursor0 for X11 desktops.
LDCONFIG="$(command -v ldconfig || echo /sbin/ldconfig)"
if [ "${XDG_SESSION_TYPE:-x11}" = "x11" ] && [ -x "$LDCONFIG" ] \
        && ! "$LDCONFIG" -p 2>/dev/null | grep -q "libxcb-cursor.so.0"; then
    echo "Missing system library: libxcb-cursor0"
    echo "Install it once with:  sudo apt install libxcb-cursor0"
    exit 1
fi
exec .venv/bin/python -m hpmultitool "$@"
