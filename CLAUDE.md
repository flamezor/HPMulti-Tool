# CLAUDE.md – HPMulti-Tool

Desktop app (Python 3.10+, PySide6/Qt6, pyqtgraph, pyserial) for data acquisition with HP/Agilent/
Keysight 34401A multimeters over RS-232 (software DTR/DSR handshake, SCPI). Module overview: see
the table in `README.md`.

## Working rules

- **Reply to the user in German.** Code, comments, commit messages and source strings are English.
- **Commit and push only when the user asks.** Releases (`gh release create`) only on request.
- Tests and screenshots must never write the real QSettings (Windows registry): patch
  `hpmultitool.gui.main_window.QSettings` to an INI file and point `APPDATA`/`XDG_DATA_HOME` to a
  temp dir (see `tests/test_front_panel_modes.py`).
- Don't delete shared temp folders (`hpmulti-*`).
- The user likes UI that only shows what is relevant for the current choice, and help texts that
  explain with formulas without being too technical.

## Commands

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\...
python -m unittest discover -s tests          # all tests, no hardware needed (simulator)
python -m pyflakes hpmultitool tests          # lint
python -m hpmultitool --simulate --lang de    # two simulated instruments
```

- Windows: if the PySide6 install fails because of long paths, create the venv at a short path.
- Screenshots on Windows: use the native platform with `WA_DontShowOnScreen`; `offscreen` has no
  fonts there.

## Conventions

- **i18n:** texts are English in `tr("…")` (or `N_("…")` in data tables); German in
  `hpmultitool/i18n_de.py`. `tests/test_i18n.py` fails on missing *and* unused entries – add and
  remove catalogue entries with every text change.
- Help pages (`gui/help_content.py`) and READMEs exist in English and German; keep both in sync.
- Number display goes through `localize_number` / `format_reading` / `format_value`.

## Domain decisions (don't change without asking)

- Evaluation per series (`analysis.py`, after the lab script "Fehler- und Ausgleichsrechnung"):
  x̄, s (n−1), s(x̄) = s/√n, Student t (two-sided, 68.27 / 95 / 99 %), **u = t·s(x̄) + h (linear
  sum)**; u rounded to 2 significant digits (ties to even), x̄ to the same place;
  `MIN_READINGS = 4`. Can be switched off per instrument (`DeviceConfig.uncertainty`).
- Instrument error h (`specs.py`) from the user's guide chapter 8, columns 24 h / 90 d / 1 y
  (default 1 y = time since last *adjustment*). Autorange assumes the smallest range that holds
  the value. 18–28 °C only.
- Removed on purpose: Pt100/Pt1000 (IEC 60751), tolerance check, moving average, drift.
  Thermocouples (IEC 60584) postponed.
- Continuity and diode test are front-panel modes: not loggable in the measurement plan
  (`functions.is_loggable`), available via "Switch instrument to this mode" and live mode.
- Stop: reads are polled in 0.2 s slices (`instrument.py`, `ReadCancelled`) followed by a device
  clear; don't switch to pyserial `cancel_read`.
- Mouse wheel never changes values (`gui/widgets.WheelGuard`).

## Status and next steps

- Version 0.1.3 is pushed but **not released**; release after the hardware test per the test
  protocol.
- Session report and test protocol live in `../Dokumentation/` next to this folder (not in the
  repo): `Sitzungsbericht_2026-11-13.md`, `Pruefprotokoll_HPMulti-Tool_v0.1.3.md`. Read the
  report first when resuming.
- Open topic: the user reviews the instruments' calibration certificate (adjusted or only
  calibrated? correction values, lab uncertainty). Idea: store correction values per instrument
  in the advanced settings (⚙) and use lab uncertainty + drift as h instead of the data-sheet
  limit. Scope to be decided after the certificate is known.
- Optional ideas, not commissioned: Windows exe (PyInstaller), optical continuity indicator in
  live mode, GUM quadrature as an option, query the actual range from the instrument, cancel a
  slow live reading on a settings change.
