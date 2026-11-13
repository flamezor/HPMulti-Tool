"""Display of readings: the large readout tile per instrument and the readings table."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..acquisition import Reading
from ..analysis import MIN_READINGS, Evaluation, derived_unit, result_text
from ..export import DeviceRecord, confidence_text, quantity_text, status_text
from ..functions import CONV_NONE, MATH_LIMIT, DeviceConfig, format_reading, format_value
from ..i18n import N_, localize_number, tr
from ..instrument import DeviceInfo
from .widgets import muted

WARN_COLOR, FAIL_COLOR = "#fbbf24", "#f87171"
NBSP = " "


class ReadoutTile(QFrame):
    def __init__(self, info: DeviceInfo, config: DeviceConfig, color: str):
        super().__init__()
        self.setObjectName("Readout")
        self.config = config
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        top = QHBoxLayout()
        name = QLabel(info.label)
        name.setObjectName("ReadoutName")
        name.setStyleSheet(f"color:{color};")
        top.addWidget(name)
        if config.label:
            obj = QLabel(config.label)
            obj.setObjectName("ReadoutObject")
            top.addWidget(obj)
        top.addWidget(muted(f"{config.func.short} · {config.range_label()}", wrap=False), 1)
        self.status = muted("", wrap=False)
        top.addWidget(self.status)
        layout.addLayout(top)
        self.value = QLabel("—")
        self.value.setObjectName("ReadoutValue")
        self.value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.value)
        self.secondary = QLabel("")
        self.secondary.setAlignment(Qt.AlignRight)
        self.secondary.setVisible(config.conversion != CONV_NONE)
        layout.addWidget(self.secondary)
        self.result = QLabel("")
        self.result.setObjectName("ReadoutResult")
        self.result.setAlignment(Qt.AlignRight)
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        # Wraps when the tile is narrow; otherwise this line alone would force the window wider.
        self.stats = muted("", wrap=True)
        self.stats.setAlignment(Qt.AlignRight)
        layout.addWidget(self.stats)

    def show_reading(self, reading: Reading, ev: Evaluation):
        cfg = self.config
        if reading.value is None:
            self.value.setText(status_text(reading.status))
        else:
            self.value.setText(format_reading(cfg, reading.value))
        if reading.status in ("LOW", "HIGH"):
            self.status.setText("⚠ " + status_text(reading.status))
        elif cfg.math == MATH_LIMIT:
            self.status.setText(tr("✓ within"))
        if cfg.conversion != CONV_NONE:
            self.secondary.setText("→ " + (format_value(reading.derived, derived_unit(cfg),
                                                        significant=cfg.digits + 1)
                                           if reading.derived is not None else "—"))
        self.show_evaluation(ev)

    def show_evaluation(self, ev: Evaluation):
        """Running measurement result x̄ ± u and the figures behind it."""
        cfg = self.config
        if not ev.n:
            return
        # Line breaks only between the parts, never inside a result.
        converted = ev.converted(cfg)
        if ev.with_uncertainty:
            parts = [f"x̄ ± u = {result_text(ev.mean, ev.u, cfg.unit)}"]
            if converted is not None:
                parts.append("→ " + result_text(converted.mean, converted.u, derived_unit(cfg)))
            parts.append(f"({confidence_text(ev.confidence)})")
        else:
            parts = [f"x̄ = {format_reading(cfg, ev.mean)}"]
            if converted is not None:
                parts.append("→ " + result_text(converted.mean, None, derived_unit(cfg)))
        text = "  ".join(part.replace(" ", NBSP) for part in parts)
        if not ev.valid:
            text = (f"<span style='color:{WARN_COLOR}'>⚠ "
                    + tr("n < {n}: scatter not evaluable", n=MIN_READINGS)
                    + f"</span><br>{text}")
        self.result.setText(text)
        parts = [f"s {quantity_text(ev.s, cfg.unit)}"]
        if ev.with_uncertainty:
            parts.append(f"h {quantity_text(ev.h, cfg.unit)}")
        parts += [f"min {format_reading(cfg, ev.minimum)}", f"max {format_reading(cfg, ev.maximum)}",
                  f"n = {ev.n}"]
        if ev.invalid:
            parts.append(tr("{n} invalid", n=ev.invalid))
        # Wrap only between the figures, never between name, value and unit.
        self.stats.setText("   ".join(part.replace(" ", NBSP) for part in parts))

    def set_status(self, text: str):
        self.status.setText(text)


class ReadingsModel(QAbstractTableModel):
    HEADERS = [N_("Time"), N_("t (s)"), N_("Step"), N_("Pt"), N_("Instrument"),
               N_("Label"), N_("Reading"), N_("Calculated"), N_("Status"), N_("Raw value")]

    def __init__(self):
        super().__init__()
        self.rows: list[tuple[DeviceRecord, Reading]] = []

    def reset(self, rows=()):
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def add(self, items):
        if not items:
            return
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
        self.rows.extend(items)
        self.endInsertRows()

    def remove_step(self, step: int):
        self.reset([(rec, r) for rec, r in self.rows if rec.step != step])

    def rowCount(self, parent=QModelIndex()):  # noqa: N802 - Qt naming
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):  # noqa: N802
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return tr(self.HEADERS[section])
        return None

    def data(self, index, role=Qt.DisplayRole):
        rec, r = self.rows[index.row()]
        col = index.column()
        cfg = rec.config
        if role == Qt.DisplayRole:
            derived = ""
            if r.derived is not None:
                derived = format_value(r.derived, derived_unit(cfg), significant=cfg.digits + 1)
            return [
                r.timestamp.strftime("%H:%M:%S.%f")[:-3], localize_number(f"{r.elapsed:.3f}"),
                str(rec.step), str(r.point), rec.info.label, cfg.label,
                format_reading(cfg, r.value) if r.value is not None else "—",
                derived, status_text(r.status), r.raw,
            ][col]
        if role == Qt.TextAlignmentRole and col in (1, 2, 3, 6, 7):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.ForegroundRole:
            if col == 8 and r.status != "OK":
                return QColor(FAIL_COLOR)
        if role == Qt.FontRole and col in (6, 7):
            font = QFont("monospace")
            font.setStyleHint(QFont.Monospace)
            return font
        return None
