"""Per-user data directories (Linux: ~/.local/share, Windows: %APPDATA%)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def autosave_dir() -> Path:
    path = data_dir() / "measurements"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_dir() -> Path:
    path = data_dir() / "calibration_backups"
    path.mkdir(parents=True, exist_ok=True)
    return path
