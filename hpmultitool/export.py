"""Measurement records and file export (.csv and .txt)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import APP_NAME, __version__
from .acquisition import Reading
from .analysis import VERDICT_FAIL, VERDICT_PASS, derive, derived_unit, statistics_of, verdict
from .functions import CONV_NONE, TOL_NONE, DeviceConfig, format_reading, format_value, number_text
from .i18n import N_, localize_number, tr
from .instrument import DeviceInfo

CSV_FORMATS = {
    "de": {"label": N_("German (Excel DE): semicolon, decimal comma"), "delimiter": ";",
           "decimal": ","},
    "intl": {"label": N_("International: comma, decimal point"), "delimiter": ",",
             "decimal": "."},
}

STATUS_TEXT = {"OK": N_("OK"), "OVERLOAD": N_("OVERLOAD"), "LOW": N_("BELOW LIMIT"),
               "HIGH": N_("ABOVE LIMIT"), "TIMEOUT": N_("TIMEOUT"), "ERROR": N_("ERROR")}
VERDICT_TEXT = {VERDICT_PASS: N_("PASS"), VERDICT_FAIL: N_("FAIL"), "": ""}


def status_text(status: str) -> str:
    return tr(STATUS_TEXT.get(status, status))


def verdict_text(value: str) -> str:
    return tr(VERDICT_TEXT.get(value, value)) if value else ""


@dataclass
class DeviceRecord:
    """Readings of one instrument for one measured object (one loop step)."""

    info: DeviceInfo
    config: DeviceConfig
    readings: list[Reading] = field(default_factory=list)
    instrument_minmax: dict | None = None
    step: int = 1
    stability_used: bool = False
    stable_value: float | None = None   # mean of the stable window
    stable_after: float | None = None   # seconds until stable

    def values(self) -> list[float]:
        return [r.value for r in self.readings if r.value is not None]

    def stats(self) -> dict:
        valid = [r for r in self.readings if r.value is not None]
        return statistics_of([r.value for r in valid], [r.elapsed for r in valid])

    def derived_stats(self) -> dict:
        valid = [r for r in self.readings if r.derived is not None]
        return statistics_of([r.derived for r in valid], [r.elapsed for r in valid])

    def verdict(self) -> tuple[str, int]:
        """Overall PASS/FAIL and number of failed readings ('' without tolerance).

        With "measure until stable" only the final (stable) value counts; a
        measurement that never became stable fails.
        """
        if self.config.tolerance == TOL_NONE or not self.readings:
            return "", 0
        if self.stability_used:
            if self.stable_value is None:
                return VERDICT_FAIL, 0
            final = self.stable_value
            return verdict(self.config, final, derive(self.config, final)), 0
        failed = sum(1 for r in self.readings if r.verdict == VERDICT_FAIL)
        return (VERDICT_FAIL if failed else VERDICT_PASS), failed

    @property
    def name(self) -> str:
        return self.config.label or self.info.label


@dataclass
class MeasurementRecord:
    devices: list[DeviceRecord]
    interval: float
    duration: float | None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    note: str = ""
    loop: bool = False
    profile: str = ""
    stability: object = None     # acquisition.Stability or None

    def rows(self):
        """All readings of all devices, ordered by step and time."""
        items = [(rec, r) for rec in self.devices for r in rec.readings]
        items.sort(key=lambda item: (item[0].step, item[1].elapsed, item[1].slot))
        return items

    def has_conversion(self) -> bool:
        return any(rec.config.conversion != CONV_NONE for rec in self.devices)

    def has_tolerance(self) -> bool:
        return any(rec.config.tolerance != TOL_NONE for rec in self.devices)


def columns(record: MeasurementRecord) -> list[str]:
    cols = [tr("Date"), tr("Time"), tr("Time since start (s)"), tr("Step"),
            tr("Point"), tr("ID"), tr("Label"), tr("Port"), tr("Function"),
            tr("Range"), tr("Resolution"), tr("Reading"), tr("Unit")]
    if record.has_conversion():
        cols += [tr("Calculated"), tr("Unit (calculated)")]
    if record.has_tolerance():
        cols.append(tr("Verdict"))
    cols += [tr("Status"), tr("Raw value")]
    return cols


def _plain(value: float | None, decimal: str, significant: int = 7) -> str:
    if value is None:
        return ""
    text = f"{value:.{significant}g}"
    return text.replace(".", decimal) if decimal != "." else text


def reading_row(record: MeasurementRecord, rec: DeviceRecord, r: Reading,
                decimal: str) -> list[str]:
    cfg = rec.config
    elapsed = f"{r.elapsed:.3f}"
    if decimal != ".":
        elapsed = elapsed.replace(".", decimal)
    row = [
        r.timestamp.strftime("%d.%m.%Y") if decimal == "," else r.timestamp.strftime("%Y-%m-%d"),
        r.timestamp.strftime("%H:%M:%S.%f")[:-3],
        elapsed, str(rec.step), str(r.point), rec.info.label, cfg.label, rec.info.port,
        tr(cfg.func.label), cfg.range_label(), cfg.resolution_label(),
        number_text(cfg, r.value, decimal), cfg.unit,
    ]
    if record.has_conversion():
        row += [_plain(r.derived, decimal, cfg.digits + 1), derived_unit(cfg)]
    if record.has_tolerance():
        row.append(verdict_text(r.verdict))
    row += [status_text(r.status), r.raw]
    return row


def write_csv(record: MeasurementRecord, path: Path, fmt: str = "de") -> None:
    options = CSV_FORMATS[fmt]
    with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=options["delimiter"])
        writer.writerow(columns(record))
        for rec, reading in record.rows():
            writer.writerow(reading_row(record, rec, reading, options["decimal"]))


def _duration_text(record: MeasurementRecord) -> str:
    if record.duration is None:
        return tr("unlimited (until stopped)")
    if record.duration == 0:
        return tr("1 reading")
    return localize_number(f"{record.duration:g}") + " s"


def summary_rows(record: MeasurementRecord) -> list[list[str]]:
    """One line per device record: step, object, device, mean, min, max, σ, n, derived, verdict."""
    rows = []
    for rec in sorted(record.devices, key=lambda r: (r.step, r.info.label)):
        cfg, stats = rec.config, rec.stats()
        verdict, failed = rec.verdict()
        if stats["count"]:
            values = [format_reading(cfg, stats["mean"]), format_reading(cfg, stats["min"]),
                      format_reading(cfg, stats["max"]),
                      format_value(stats["std"], cfg.unit, significant=3)
                      if stats["count"] > 1 else "—"]
        else:
            values = ["—"] * 4
        derived = ""
        if cfg.conversion != CONV_NONE:
            dstats = rec.derived_stats()
            if dstats["count"]:
                derived = format_value(dstats["mean"], derived_unit(cfg),
                                       significant=cfg.digits + 1)
        text = verdict_text(verdict)
        if failed:
            text += f" ({failed}/{len(rec.readings)})"
        final = after = ""
        if rec.stability_used:
            if rec.stable_value is not None:
                final = format_reading(cfg, rec.stable_value)
                after = localize_number(f"{rec.stable_after:.1f}") + " s"
            else:
                after = tr("not stable")
        rows.append([str(rec.step), cfg.label or "—", rec.info.label, *values,
                     str(stats["count"]), derived, final, after, text])
    return rows


SUMMARY_HEADERS = [N_("Step"), N_("Label"), N_("Instrument"), N_("Mean"),
                   N_("Minimum"), N_("Maximum"), N_("σ"), N_("n"), N_("Calculated"),
                   N_("Final value (stable)"), N_("Stable after"), N_("Verdict")]


def write_txt(record: MeasurementRecord, path: Path) -> None:
    out = io.StringIO()
    line = "=" * 92
    out.write(f"{line}\n{APP_NAME} {__version__} – {tr('Measurement report')}\n{line}\n")
    if record.started_at:
        out.write(f"{tr('Start:'):<18}{record.started_at:%d.%m.%Y %H:%M:%S}\n")
    if record.finished_at:
        out.write(f"{tr('End:'):<18}{record.finished_at:%d.%m.%Y %H:%M:%S}\n")
    interval = (tr("as fast as possible") if record.interval <= 0
                else localize_number(f"{record.interval:g}") + " s")
    out.write(f"{tr('Interval:'):<18}{interval}\n")
    label = tr("Duration per step:") if record.loop else tr("Duration:")
    out.write(f"{label:<18}{_duration_text(record)}\n")
    if record.loop:
        out.write(f"{tr('Mode:'):<18}{tr('Measurement series (loop)')}\n")
    if record.stability is not None:
        st = record.stability
        limit = localize_number(f"{st.limit:g}") + (" %" if st.relative else "")
        out.write(f"{tr('Until stable:'):<18}"
                  f"{tr('spread of the last {n} readings ≤ {limit}', n=st.window, limit=limit)}\n")
    if record.profile:
        out.write(f"{tr('Test profile:'):<18}{record.profile}\n")
    if record.note:
        out.write(f"{tr('Note:'):<18}{record.note}\n")

    # summary table (useful for loops and multiple devices)
    if len(record.devices) > 1:
        out.write(f"\n--- {tr('Summary')} ---\n")
        headers = [tr(h) for h in SUMMARY_HEADERS]
        rows = summary_rows(record)
        keep = [i for i in range(len(headers)) if i < 8 or any(row[i] for row in rows)]
        widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in keep]
        out.write("  ".join(headers[i].ljust(w) for i, w in zip(keep, widths)).rstrip() + "\n")
        out.write("  ".join("-" * w for w in widths) + "\n")
        for row in rows:
            out.write("  ".join(row[i].ljust(w) for i, w in zip(keep, widths)).rstrip() + "\n")

    for rec in record.devices:
        info, cfg = rec.info, rec.config
        title = f"{info.label} · {tr('Step')} {rec.step}" if record.loop else info.label
        out.write(f"\n--- {tr('Instrument')} {title} ---\n")
        port = info.port + (f"  (USB {info.usb_serial})" if info.usb_serial else "")
        out.write(f"  {tr('Port'):<22}{port}\n")
        out.write(f"  {tr('Identification'):<22}{info.identification}\n")
        if cfg.label:
            out.write(f"  {tr('Label'):<22}{cfg.label}\n")
        for key, value in cfg.summary().items():
            out.write(f"  {key:<22}{value}\n")
        stats = rec.stats()
        counts = tr("{valid} valid, {total} total", valid=stats["count"],
                    total=len(rec.readings))
        out.write(f"  {tr('Readings'):<22}{counts}\n")
        if stats["count"]:
            for key, name in (("min", N_("Minimum")), ("max", N_("Maximum")), ("mean", N_("Mean"))):
                out.write(f"  {tr(name):<22}{format_reading(cfg, stats[key])}\n")
            for key, name in (("std", N_("Standard deviation")), ("pp", N_("Peak-to-peak"))):
                out.write(f"  {tr(name):<22}{format_value(stats[key], cfg.unit, significant=3)}\n")
            if "drift" in stats:
                drift = format_value(stats["drift"], cfg.unit, significant=3)
                out.write(f"  {tr('Drift'):<22}{drift}/min\n")
        if cfg.conversion != CONV_NONE:
            dstats = rec.derived_stats()
            if dstats["count"]:
                unit, sig = derived_unit(cfg), cfg.digits + 1
                out.write(f"  {tr('Calculated mean'):<22}"
                          f"{format_value(dstats['mean'], unit, significant=sig)}"
                          f"  (min {format_value(dstats['min'], unit, significant=sig)},"
                          f" max {format_value(dstats['max'], unit, significant=sig)})\n")
        if rec.stability_used:
            if rec.stable_value is not None:
                after = localize_number(f"{rec.stable_after:.1f}")
                out.write(f"  {tr('Final value (stable)'):<22}{format_reading(cfg, rec.stable_value)}"
                          f"  ({tr('stable after {s} s', s=after)})\n")
            else:
                out.write(f"  {tr('Final value (stable)'):<22}{tr('not stable')}\n")
        verdict, failed = rec.verdict()
        if verdict:
            extra = f"  ({failed}/{len(rec.readings)})" if failed else ""
            out.write(f"  {tr('Verdict'):<22}{verdict_text(verdict)}{extra}\n")
        if rec.instrument_minmax:
            mm = rec.instrument_minmax
            out.write(f"  {tr('Min/max (instrument)'):<22}min {mm.get('min')}, max {mm.get('max')}, "
                      f"avg {mm.get('avg')}, n {mm.get('count')}\n")

    out.write(f"\n{line}\n")
    conv = record.has_conversion()
    tol = record.has_tolerance()
    header = (f"{tr('Date'):<11}{tr('Time'):<13}{tr('t (s)'):>9}  {tr('Step'):>7} "
              f"{tr('Pt'):>5}  {tr('ID'):<10}{tr('Label'):<14}{tr('Reading'):>16}")
    if conv:
        header += f"  {tr('Calculated'):>14}"
    if tol:
        header += f"  {tr('Verdict'):<9}"
    header += f"  {tr('Status')}"
    out.write(header + "\n" + "-" * len(header) + "\n")
    for rec, r in record.rows():
        cfg = rec.config
        value = format_reading(cfg, r.value) if r.value is not None else "—"
        text = (f"{r.timestamp:%d.%m.%Y} {r.timestamp:%H:%M:%S}."
                f"{r.timestamp.microsecond // 1000:03d}"
                f"{localize_number(f'{r.elapsed:.3f}'):>10}  {rec.step:>7} {r.point:>5}  "
                f"{rec.info.label:<10}{(cfg.label or '')[:13]:<14}{value:>16}")
        if conv:
            derived = (format_value(r.derived, derived_unit(cfg), significant=cfg.digits + 1)
                       if r.derived is not None else "")
            text += f"  {derived:>14}"
        if tol:
            text += f"  {verdict_text(r.verdict):<9}"
        out.write(text + f"  {status_text(r.status)}\n")
    Path(path).write_text(out.getvalue(), encoding="utf-8")


class LiveCsvWriter:
    """Crash-safe autosave: one row per reading, flushed immediately."""

    def __init__(self, path: Path, record: MeasurementRecord, fmt: str = "de"):
        self.path = Path(path)
        self.record = record
        self.options = CSV_FORMATS[fmt]
        self._handle = self.path.open("x", newline="", encoding="utf-8-sig")
        self._writer = csv.writer(self._handle, delimiter=self.options["delimiter"])
        self._writer.writerow(columns(record))
        self._handle.flush()

    def add(self, rec: DeviceRecord, reading: Reading):
        self._writer.writerow(reading_row(self.record, rec, reading, self.options["decimal"]))
        self._handle.flush()

    def close(self):
        if not self._handle.closed:
            self._handle.close()
