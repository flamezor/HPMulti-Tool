"""Test profiles: a complete setup (measurement plan + settings per instrument).

Profiles are JSON files in the user's data folder (``profiles/``), so they can
be copied between computers. Instrument settings are stored with the
instrument ID they were made for; when a profile is loaded, settings are
matched by ID first and then assigned to the remaining instruments in order.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import __version__
from .functions import DeviceConfig
from .paths import data_dir

PROFILE_FORMAT = "HPMULTITOOL_PROFILE_V1"


def profile_dir() -> Path:
    path = data_dir() / "profiles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _file_name(name: str) -> str:
    stem = re.sub(r"[^\w.-]+", "_", name.strip(), flags=re.UNICODE).strip("._")
    return (stem or "profile") + ".json"


def profile_path(name: str) -> Path:
    return profile_dir() / _file_name(name)


def list_profiles() -> list[tuple[str, Path]]:
    """(display name, path) of all readable profiles, sorted by name."""
    result = []
    for path in profile_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("format") == PROFILE_FORMAT:
            result.append((str(data.get("name") or path.stem), path))
    return sorted(result, key=lambda item: item[0].lower())


def save_profile(name: str, plan: dict, devices: list[dict]) -> Path:
    """Write a profile. ``devices``: [{"id": str, "use": bool, "config": dict}, ...]."""
    if not name.strip():
        raise ValueError("empty profile name")
    data = {
        "format": PROFILE_FORMAT,
        "name": name.strip(),
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "app_version": __version__,
        "plan": plan,
        "devices": devices,
    }
    path = profile_path(name)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_profile(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != PROFILE_FORMAT:
        raise ValueError("not a HPMulti-Tool profile")
    data.setdefault("plan", {})
    devices = []
    for entry in data.get("devices", []):
        if isinstance(entry, dict) and isinstance(entry.get("config"), dict):
            devices.append({"id": str(entry.get("id", "")), "use": bool(entry.get("use", True)),
                            "config": DeviceConfig.from_dict(entry["config"])})
    data["devices"] = devices
    return data


def assign_configs(profile_devices: list[dict], device_ids: list[str]) -> dict[str, dict]:
    """Map connected instrument IDs to profile entries: same ID first, then in order."""
    result: dict[str, dict] = {}
    remaining = list(profile_devices)
    for device_id in device_ids:
        match = next((entry for entry in remaining if entry["id"] == device_id), None)
        if match is not None:
            result[device_id] = match
            remaining.remove(match)
    for device_id in device_ids:
        if device_id not in result and remaining:
            result[device_id] = remaining.pop(0)
    return result


def delete_profile(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
