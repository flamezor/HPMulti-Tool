"""Back up and change the instrument ID stored in the calibration message.

The 34401A has no serial number over *IDN?. The calibration message
(CAL:STRing, up to 40 characters, 12 shown on the display) is used as
the unique instrument ID. Writing it requires calibration security to be
off; this module unlocks with the user's security code, writes, verifies,
and always tries to lock again. A JSON backup (format compatible with the
earlier calibration_backup.py) is written before every change.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .instrument import DeviceInfo, InstrumentError, encode_scpi_string, open_instrument
from .i18n import tr
from .paths import backup_dir

BACKUP_FORMAT = "HP34401A_CAL_STRING_BACKUP_V1"
DEFAULT_SECURITY_CODE = "HP034401"
MAX_LENGTH = 40
DISPLAY_LENGTH = 12


def validate_id(text: str) -> list[str]:
    """Return blocking problems for a new ID."""
    problems = []
    if not text.strip():
        problems.append(tr("The ID must not be empty."))
    if len(text) > MAX_LENGTH:
        problems.append(tr("At most {n} characters.", n=MAX_LENGTH))
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in text):
        problems.append(tr("Printable ASCII characters only (no umlauts)."))
    return problems


def validate_security_code(code: str) -> bool:
    return 1 <= len(code) <= 12 and code.isascii() and code.isalnum() and code[0].isalpha()


def save_backup(meter, port: str, purpose: str) -> Path:
    raw = meter.query("CAL:STR?")
    from .instrument import decode_scpi_string
    record = {
        "format": BACKUP_FORMAT,
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": purpose,
        "port_at_backup": port,
        "identification": meter.identify(),
        "calibration_message": decode_scpi_string(raw),
        "calibration_message_raw": raw,
        "calibration_count": meter.query("CAL:COUN?"),
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_port = re.sub(r"[^A-Za-z0-9._-]", "_", port)
    path = backup_dir() / f"{stamp}_{safe_port}_{purpose}.json"
    with path.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
    return path


def write_device_id(info: DeviceInfo, new_id: str, security_code: str, log=print) -> Path:
    """Change the stored ID. Returns the path of the safety backup."""
    problems = validate_id(new_id)
    if problems:
        raise ValueError(" ".join(problems))
    if not validate_security_code(security_code):
        raise ValueError(tr("Security code: 1–12 letters/digits, starting with a letter."))

    meter = open_instrument(info)
    try:
        meter.connect()
        current = meter.calibration_message()
        if current != info.calibration_message:
            raise InstrumentError(tr("Port {port} reports {found!r} instead of {expected!r}. "
                                     "Aborted, nothing written.", port=info.port,
                                     found=current, expected=info.calibration_message))
        count_before = meter.calibration_count()
        was_secured = meter.calibration_secured()
        meter.check_errors(tr("Existing instrument errors"))
        backup = save_backup(meter, info.port, "pre_id_write")
        log(tr("Backup saved: {path}", path=backup))

        unlocked = False
        try:
            if was_secured:
                meter.write(f"CAL:SEC:STAT OFF,{security_code}")
                if meter.calibration_secured():
                    errors = meter.read_errors()
                    raise InstrumentError(tr(
                        "Could not disable calibration security – wrong security code? {errors} "
                        "Nothing written.", errors="; ".join(errors)))
                unlocked = True
                log(tr("Calibration security temporarily disabled."))
            meter.write(f"CAL:STR {encode_scpi_string(new_id)}")
            meter.check_errors(tr("Writing the ID"))
            stored = meter.calibration_message()
            if stored != new_id:
                raise InstrumentError(tr("Verification failed: instrument reports {value!r}.", value=stored))
            count_after = meter.calibration_count()
            if count_after != count_before:
                raise InstrumentError(tr("Calibration count changed ({a} → {b}).",
                                         a=count_before, b=count_after))
            log(tr("New ID verified: {value!r}. Calibration count unchanged ({count}).",
                   value=stored, count=count_after))
        finally:
            if unlocked:
                meter.write(f"CAL:SEC:STAT ON,{security_code}")
                if not meter.calibration_secured():
                    raise InstrumentError(tr(
                        "CRITICAL: calibration security could not be enabled again! Do not use "
                        "the instrument until CAL:SEC:STAT has been checked."))
                meter.check_errors(tr("Restoring calibration security"))
                log(tr("Calibration security enabled again."))
        info.calibration_message = new_id
        return backup
    finally:
        meter.close()
