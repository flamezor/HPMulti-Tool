"""Display of readings: the large readout tile per instrument and the readings table."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..acquisition import Reading
from ..analysis import VERDICT_PASS, derived_unit
from ..export import DeviceRecord, status_text, verdict_text
from ..functions import CONV_NONE, MATH_LIMIT, TOL_NONE, DeviceConfig, format_reading, format_value
from ..i18n import N_, localize_number, tr
from ..instrument import DeviceInfo
from .widgets import muted

PASS_COLOR, FAIL_COLOR = "#34d399", "#f87171"


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
        self.secondary.setVisible(config.conversion != CONV_NONE or config.tolerance != TOL_NONE)
        layout.addWidget(self.secondary)
        self.stats = muted("", wrap=False)
        self.stats.setAlignment(Qt.AlignRight)
        layout.addWidget(self.stats)

    def show_reading(self, reading: Reading, stats: dict):
        cfg = self.config
        if reading.value is None:
            self.value.setText(status_text(reading.status))
        else:
            self.value.setText(format_reading(cfg, reading.value))
        if reading.status in ("LOW", "HIGH"):
            self.status.setText("⚠ " + status_text(reading.status))
        elif cfg.math == MATH_LIMIT:
            self.status.setText(tr("✓ within"))
        parts = []
        if cfg.conversion != CONV_NONE:
            parts.append("→ " + (format_value(reading.derived, derived_unit(cfg),
                                              significant=cfg.digits + 1)
                                 if reading.derived is not None else "—"))
        if reading.verdict:
            color = PASS_COLOR if reading.verdict == VERDICT_PASS else FAIL_COLOR
            parts.append(f"<span style='color:{color}; font-weight:700'>"
                         f"{verdict_text(reading.verdict)}</span>")
        self.secondary.setText("   ".join(parts))
        if stats.get("count"):
            def fmt(v):
                return format_reading(cfg, v)
            text = f"min {fmt(stats['min'])}   max {fmt(stats['max'])}   Ø {fmt(stats['mean'])}"
            if stats["count"] > 1:
                text += f"   σ {format_value(stats['std'], cfg.unit, significant=3)}"
            if "drift" in stats:
                text += (f"   {tr('Drift')} "
                         f"{format_value(stats['drift'], cfg.unit, significant=2)}/min")
            self.stats.setText(text + f"   n = {stats['count']}")

    def set_status(self, text: str):
        self.status.setText(text)


class ReadingsModel(QAbstractTableModel):
    HEADERS = [N_("Time"), N_("t (s)"), N_("Step"), N_("Pt"), N_("Instrument"),
               N_("Label"), N_("Reading"), N_("Calculated"), N_("Verdict"),
               N_("Status"), N_("Raw value")]

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
                derived, verdict_text(r.verdict), status_text(r.status), r.raw,
            ][col]
        if role == Qt.TextAlignmentRole and col in (1, 2, 3, 6, 7):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.ForegroundRole:
            if col == 9 and r.status != "OK":
                return QColor(FAIL_COLOR)
            if col == 8 and r.verdict:
                return QColor(PASS_COLOR if r.verdict == VERDICT_PASS else FAIL_COLOR)
        if role == Qt.FontRole and col in (6, 7):
            font = QFont("monospace")
            font.setStyleHint(QFont.Monospace)
            return font
        return None
