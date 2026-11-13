"""Measurement records and file export (.csv and .txt)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import APP_NAME, __version__
from .acquisition import Reading
from .analysis import MIN_READINGS, Evaluation, derived_unit, evaluate, result_text
from .functions import (CONFIDENCE_LEVELS, CONV_NONE, DeviceConfig, format_reading, format_value,
                        number_text)
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


def status_text(status: str) -> str:
    return tr(STATUS_TEXT.get(status, status))


def confidence_text(confidence: float) -> str:
    return tr(dict(CONFIDENCE_LEVELS).get(confidence, f"{confidence:g} %"))


def quantity_text(value: float | None, unit: str) -> str:
    """An uncertainty or deviation with two significant digits; '—' if unknown."""
    return "—" if value is None else format_value(value, unit, significant=2)


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

    def evaluation(self) -> Evaluation:
        """Measurement result x̄ ± u of the valid readings (see analysis.evaluate)."""
        values = self.values()
        return evaluate(values, self.config, invalid=len(self.readings) - len(values))

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


def columns(record: MeasurementRecord) -> list[str]:
    cols = [tr("Date"), tr("Time"), tr("Time since start (s)"), tr("Step"),
            tr("Point"), tr("ID"), tr("Label"), tr("Port"), tr("Function"),
            tr("Range"), tr("Resolution"), tr("Reading"), tr("Unit")]
    if record.has_conversion():
        cols += [tr("Calculated"), tr("Unit (calculated)")]
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


def evaluation_notes(ev: Evaluation) -> str:
    """Short hint for the overview: why a result is not (fully) valid."""
    hints = []
    if ev.n and not ev.valid:
        hints.append(tr("n < {n}", n=MIN_READINGS))
    if ev.n and ev.with_uncertainty and ev.h is None:
        hints.append(tr("h not specified"))
    if ev.invalid:
        hints.append(tr("{n} invalid", n=ev.invalid))
    return " · ".join(hints)


def summary_rows(record: MeasurementRecord) -> list[list[str]]:
    """One line per device record with the measurement result x̄ ± u (see SUMMARY_HEADERS)."""
    rows = []
    for rec in sorted(record.devices, key=lambda r: (r.step, r.info.label)):
        cfg, ev = rec.config, rec.evaluation()
        unit = cfg.unit
        if ev.n:
            relative = (localize_number(f"{ev.relative:.2g}") + " %"
                        if ev.relative is not None else "—")
            values = [format_reading(cfg, ev.mean), quantity_text(ev.s, unit),
                      quantity_text(ev.sem, unit),
                      localize_number(f"{ev.t:.2f}") if ev.t is not None else "—",
                      quantity_text(ev.h, unit), quantity_text(ev.u, unit),
                      result_text(ev.mean, ev.u, unit), relative,
                      format_reading(cfg, ev.minimum), format_reading(cfg, ev.maximum)]
            if not ev.with_uncertainty:
                values[3:8] = [""] * 5   # t, h, u, x̄ ± u, u rel.: switched off
        else:
            values = ["—"] * 10
        converted = ev.converted(cfg)
        derived = (result_text(converted.mean, converted.u, derived_unit(cfg))
                   if converted is not None else "")
        final = after = ""
        if rec.stability_used:
            if rec.stable_value is not None:
                final = format_reading(cfg, rec.stable_value)
                after = localize_number(f"{rec.stable_after:.1f}") + " s"
            else:
                after = tr("not stable")
        rows.append([str(rec.step), cfg.label or "—", rec.info.label, str(ev.n), *values,
                     derived, final, after, evaluation_notes(ev)])
    return rows


SUMMARY_HEADERS = [N_("Step"), N_("Label"), N_("Instrument"), N_("n"), N_("Mean x̄"),
                   N_("s"), N_("s(x̄)"), N_("t"), N_("h (instrument)"), N_("u"),
                   N_("Result x̄ ± u"), N_("u rel."), N_("Minimum"), N_("Maximum"),
                   N_("Result (calculated)"), N_("Final value (stable)"), N_("Stable after"),
                   N_("Note")]
SUMMARY_ALWAYS = 14   # the following columns are left out when empty
UNCERTAINTY_COLUMNS = range(7, 12)   # t … u rel.: empty when the uncertainty is switched off
_OPTIONAL_COLUMNS = set(UNCERTAINTY_COLUMNS) | set(range(SUMMARY_ALWAYS, len(SUMMARY_HEADERS)))


def summary_columns(rows: list[list[str]]) -> list[int]:
    """Indices of the summary columns to show: optional columns only when used."""
    return [i for i in range(len(SUMMARY_HEADERS))
            if i not in _OPTIONAL_COLUMNS or any(row[i] for row in rows)]


def evaluation_lines(rec: DeviceRecord) -> list[tuple[str, str]]:
    """The measurement result of one record as (label, text) pairs for the report."""
    cfg, ev = rec.config, rec.evaluation()
    unit = cfg.unit
    lines = [(tr("Readings"), tr("{valid} valid, {total} total", valid=ev.n,
                                  total=len(rec.readings)))]
    if not ev.n:
        return lines
    spread = quantity_text(ev.spread, unit)
    lines += [
        (tr("Mean x̄"), format_reading(cfg, ev.mean)),
        (tr("Minimum / maximum"), f"{format_reading(cfg, ev.minimum)} / "
                                   f"{format_reading(cfg, ev.maximum)}  ({tr('spread')} {spread})"),
        (tr("Std. deviation s"), quantity_text(ev.s, unit)),
        (tr("Std. dev. of mean"), quantity_text(ev.sem, unit)),
    ]
    converted = ev.converted(cfg)
    if not ev.with_uncertainty:
        lines.append((tr("Uncertainty u"), tr("not calculated (switched off)")))
        if converted is not None:
            lines.append((tr("Result (calculated)"),
                          result_text(converted.mean, None, derived_unit(cfg))))
        return lines
    t_text = localize_number(f"{ev.t:.3f}") if ev.t is not None else "—"
    u_text = quantity_text(ev.u, unit)
    if ev.relative is not None:
        u_text += "  (" + localize_number(f"{ev.relative:.2g}") + " %)"
    lines += [
        (tr("Student t"), f"{t_text}  ({confidence_text(ev.confidence)}, n = {ev.n})"),
        (tr("Random part t·s(x̄)"), quantity_text(ev.random, unit)),
        (tr("Instrument error h"), quantity_text(ev.h, unit)),
        (tr("Uncertainty u"), u_text),
        (tr("Result"), result_text(ev.mean, ev.u, unit)
         + ("" if ev.valid else "  " + tr("(not valid)"))),
    ]
    if converted is not None:
        lines.append((tr("Result (calculated)"),
                      result_text(converted.mean, converted.u, derived_unit(cfg))))
    for note in ev.notes:
        lines.append((tr("Note"), tr(note)))
    return lines


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
        keep = summary_columns(rows)
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
        for key, value in evaluation_lines(rec):
            out.write(f"  {key:<22}{value}\n")
        if rec.stability_used:
            if rec.stable_value is not None:
                after = localize_number(f"{rec.stable_after:.1f}")
                out.write(f"  {tr('Final value (stable)'):<22}{format_reading(cfg, rec.stable_value)}"
                          f"  ({tr('stable after {s} s', s=after)})\n")
            else:
                out.write(f"  {tr('Final value (stable)'):<22}{tr('not stable')}\n")
        if rec.instrument_minmax:
            mm = rec.instrument_minmax
            out.write(f"  {tr('Min/max (instrument)'):<22}min {mm.get('min')}, max {mm.get('max')}, "
                      f"avg {mm.get('avg')}, n {mm.get('count')}\n")

    out.write(f"\n{line}\n")
    conv = record.has_conversion()
    header = (f"{tr('Date'):<11}{tr('Time'):<13}{tr('t (s)'):>9}  {tr('Step'):>7} "
              f"{tr('Pt'):>5}  {tr('ID'):<10}{tr('Label'):<14}{tr('Reading'):>16}")
    if conv:
        header += f"  {tr('Calculated'):>14}"
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
