"""Main window of HPMulti-Tool."""

from __future__ import annotations

import json
import queue
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QRectF, QSettings, QThreadPool,
                            QTimer, Qt,
                            QUrl, Signal)
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QImage, QKeySequence,
                           QPainter)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDoubleSpinBox,
                               QFileDialog, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QLineEdit, QSpinBox,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSplitter,
                               QStackedWidget, QTableView, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..acquisition import Plan, Reading, Session, Stability, set_mode_only
from ..analysis import VERDICT_PASS, derived_unit, moving_average
from ..export import (CSV_FORMATS, SUMMARY_HEADERS, DeviceRecord, LiveCsvWriter,
                      MeasurementRecord, status_text, summary_rows, verdict_text, write_csv,
                      write_txt)
from ..functions import (CONV_NONE, MATH_LIMIT, TOL_ABSOLUTE, TOL_NONE, TOL_PERCENT, TOL_RANGE,
                         DeviceConfig, configuration_commands, estimated_reading_time,
                         format_reading, format_value, validate)
from ..i18n import LANGUAGES, N_, language, localize_number, tr
from ..instrument import DeviceInfo, discover
from ..paths import autosave_dir
from ..profiles import (assign_configs, delete_profile, list_profiles, load_profile, profile_dir,
                        save_profile)
from .advanced_dialog import AdvancedDialog
from .device_panel import DeviceSettingsPanel
from .help_dialog import HelpDialog
from .live_page import LivePage
from .plotting import ClockAxis
from .icon import app_icon
from .style import DEVICE_COLORS, THEMES, checkmark_file, stylesheet
from .widgets import Card, DataCombo, FormRow, StatusDot, Task, hint, muted, section_label

DURATION_PRESETS = [(None, N_("Unlimited (until stopped)")), (0, N_("1 reading (single measurement)")),
                    (10, N_("10 seconds")), (30, N_("30 seconds")), (60, N_("1 minute")),
                    (120, N_("2 minutes")), (300, N_("5 minutes")), (600, N_("10 minutes")),
                    (1800, N_("30 minutes")), (3600, N_("1 hour")), (7200, N_("2 hours")),
                    (28800, N_("8 hours")), (86400, N_("24 hours")),
                    (-1, N_("Custom …"))]
INTERVAL_PRESETS = [(0, N_("As fast as possible")), (0.1, N_("0.1 s")), (0.2, N_("0.2 s")),
                    (0.5, N_("0.5 s")), (1, "1 s"), (2, "2 s"), (5, "5 s"), (10, "10 s"),
                    (30, "30 s"), (60, "1 min"), (300, "5 min"), (600, "10 min"),
                    (-1, N_("Custom …"))]
TIME_UNITS = [(1, "s"), (60, "min"), (3600, "h")]

MODE_SINGLE, MODE_LOOP = "single", "loop"
LOOP_TEMPLATES = [
    (N_("Sensor cable, 6 cores"), N_("red, yellow, black, white, green, brown")),
    (N_("4 cores (DIN 47100)"), N_("white, brown, green, yellow")),
    (N_("Core colours IEC 60757 (10)"),
     N_("black, brown, red, orange, yellow, green, blue, violet, grey, white")),
    (N_("Numbered 1 … 8"), "1, 2, 3, 4, 5, 6, 7, 8"),
]
ADVANCE_CONFIRM, ADVANCE_AUTO = "confirm", "auto"


def _hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _items(presets):
    return [(value, tr(text)) for value, text in presets]


# ---------------------------------------------------------------------------
class TimeInput(QWidget):
    """Preset combo plus custom value/unit fields."""

    changed = Signal()

    def __init__(self, presets, default):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.combo = DataCombo()
        self.combo.set_items(_items(presets), default)
        self.value = QDoubleSpinBox()
        self.value.setRange(0.001, 1e6)
        self.value.setDecimals(3)
        self.value.setValue(1)
        self.unit = DataCombo()
        self.unit.set_items(TIME_UNITS, 1)
        self.custom = QWidget()
        row = QHBoxLayout(self.custom)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.value, 1)
        row.addWidget(self.unit)
        layout.addWidget(self.combo)
        layout.addWidget(self.custom)
        self.combo.currentIndexChanged.connect(self._changed)
        self.value.valueChanged.connect(self._changed)
        self.unit.currentIndexChanged.connect(self._changed)
        self._changed()

    def _changed(self):
        self.custom.setVisible(self.combo.currentData() == -1)
        self.changed.emit()

    def seconds(self):
        data = self.combo.currentData()
        if data == -1:
            return self.value.value() * self.unit.currentData()
        return data

    def set_seconds(self, seconds):
        if not self.combo.select_data(seconds):
            self.combo.select_data(-1)
            factor = 1
            for factor, _ in reversed(TIME_UNITS):
                if seconds >= factor and abs(seconds / factor - round(seconds / factor, 3)) < 1e-9:
                    break
            self.unit.select_data(factor)
            self.value.setValue(seconds / factor)


# ---------------------------------------------------------------------------
class DeviceRow(QFrame):
    selected = Signal(object)
    advanced = Signal(object)
    toggled = Signal()

    def __init__(self, info: DeviceInfo, color: str):
        super().__init__()
        self.info = info
        self.setObjectName("DeviceRow")
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 6, 8)
        self.use = QCheckBox()
        self.use.setChecked(True)
        self.use.setToolTip(tr("Use this instrument for the measurement"))
        self.use.toggled.connect(self.toggled)
        bar = QFrame()
        bar.setFixedSize(4, 36)
        bar.setStyleSheet(f"background:{color}; border-radius:2px;")
        text = QVBoxLayout()
        text.setSpacing(0)
        self.name = QLabel()
        self.name.setObjectName("DeviceName")
        self.sub = muted("", wrap=True)
        text.addWidget(self.name)
        text.addWidget(self.sub)
        self.dot = StatusDot()
        self.dot.set_state("ok")
        gear = QToolButton()
        gear.setText("⚙")
        gear.setToolTip(tr("Advanced settings (ID, diagnostics)"))
        gear.clicked.connect(lambda: self.advanced.emit(self.info))
        layout.addWidget(self.use)
        layout.addWidget(bar)
        layout.addLayout(text, 1)
        layout.addWidget(self.dot)
        layout.addWidget(gear)
        self.refresh()

    def refresh(self):
        info = self.info
        self.name.setText(info.label)
        parts = [info.port]
        if info.usb_serial:
            parts.append(f"USB {info.usb_serial}")
        if info.terminals:
            parts.append(tr("Front") if info.terminals.startswith("FRON") else tr("Rear"))
        self.sub.setText(" · ".join(parts))
        tip = [info.identification, tr("Calibration count: {n}", n=info.calibration_count)]
        if not (info.calibration_message or "").strip():
            tip.append(tr("No ID stored – please assign one under ⚙."))
        self.setToolTip("\n".join(tip))

    def set_selected(self, selected: bool):
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self.selected.emit(self.info)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
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
            color = "#34d399" if reading.verdict == VERDICT_PASS else "#f87171"
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


# ---------------------------------------------------------------------------
class ReadingsModel(QAbstractTableModel):
    HEADERS = [N_("Time"), N_("t (s)"), N_("Step"), N_("Pt"), N_("Instrument"),
               N_("Label"), N_("Reading"), N_("Calculated"), N_("Verdict"),
               N_("Status"), N_("Raw value")]

    def __init__(self):
        super().__init__()
        self.rows: list[tuple[DeviceRecord, Reading]] = []

    def reset(self):
        self.beginResetModel()
        self.rows = []
        self.endResetModel()

    def add(self, items):
        if not items:
            return
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(items) - 1)
        self.rows.extend(items)
        self.endInsertRows()

    def remove_step(self, step: int):
        self.beginResetModel()
        self.rows = [(rec, r) for rec, r in self.rows if rec.step != step]
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
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
                return QColor("#f87171")
            if col == 8 and r.verdict:
                return QColor("#34d399" if r.verdict == VERDICT_PASS else "#f87171")
        if role == Qt.FontRole and col in (6, 7):
            font = QFont("monospace")
            font.setStyleHint(QFont.Monospace)
            return font
        return None


# ---------------------------------------------------------------------------
@dataclass
class LoopState:
    """Progress of a measurement series (loop) over several objects."""

    steps: list[list[tuple[DeviceInfo, DeviceConfig]]]
    advance: str
    pause: float
    index: int = 0
    countdown_end: float | None = None
    ending: bool = False

    @property
    def total(self) -> int:
        return len(self.steps)


def build_loop_steps(devices: list[tuple[DeviceInfo, DeviceConfig]], objects: list[str]):
    """Distribute objects over the selected devices: n devices measure n objects per step."""
    steps = []
    count = len(devices)
    for start in range(0, len(objects), count):
        chunk = objects[start:start + count]
        step = []
        for (info, config), name in zip(devices, chunk):
            per_object = DeviceConfig.from_dict(config.to_dict())
            per_object.label = name
            step.append((info, per_object))
        steps.append(step)
    return steps


# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    language_change_requested = Signal(str)

    def __init__(self, simulate: bool = False, devices: list[DeviceInfo] | None = None):
        super().__init__()
        self.simulate = simulate
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.theme = self.settings.value("ui/theme", "dark")
        self.pool = QThreadPool.globalInstance()
        self._tasks = set()
        self.devices: list[DeviceInfo] = []
        self.rows: list[DeviceRow] = []
        self.panels: dict[str, DeviceSettingsPanel] = {}
        self.session: Session | None = None
        self.record: MeasurementRecord | None = None
        self.writer: LiveCsvWriter | None = None
        self.loop: LoopState | None = None
        self.tiles: list[ReadoutTile] = []
        self.curves = []
        self.avg_curves = []
        self.plot_data: list[tuple[list, list]] = []
        self.slot_records: list[DeviceRecord] = []
        self._plot_dirty = False
        self._errors: list[str] = []
        self._start_time = None

        self.setWindowTitle(f"{APP_NAME}  –  HP 34401A" + ("  [Simulation]" if simulate else ""))
        self.setWindowIcon(app_icon())
        self.resize(1600, 960)
        self._build()
        self.apply_theme(self.theme)
        geometry = self.settings.value("ui/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._poll_session)
        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(300)
        self.plot_timer.timeout.connect(self._refresh_plot)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(200)
        self.countdown_timer.timeout.connect(self._countdown_tick)
        if devices is not None:
            QTimer.singleShot(0, lambda: self._devices_found(list(devices)))
        else:
            QTimer.singleShot(150, self.scan_devices)

    # ================================================================ layout
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_settings_area())
        splitter.addWidget(self._build_results_area())
        splitter.setSizes([390, 440, 770])
        splitter.setStretchFactor(2, 1)
        wrapper = QWidget()
        lay = QVBoxLayout(wrapper)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(splitter)
        self.pages = QStackedWidget()
        self.pages.addWidget(wrapper)
        self.live_page = LivePage(self)
        self.live_page.running_changed.connect(self._live_running_changed)
        self.live_page.record_ready.connect(self._live_record_ready)
        self.pages.addWidget(self.live_page)
        root.addWidget(self.pages, 1)
        self.statusBar().showMessage(tr("Ready"))

        for text, key, slot in ((tr("Scan for instruments"), "F5", self.scan_devices),
                                (tr("Help"), "F1", self.show_help)):
            action = QAction(text, self, shortcut=QKeySequence(key))
            action.triggered.connect(slot)
            self.addAction(action)

    def _build_header(self):
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 10, 18, 10)
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(34, 34))
        icon.setStyleSheet("background:transparent;")
        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")
        subtitle = QLabel(tr("Data acquisition for the HP 34401A · v{version}", version=__version__))
        subtitle.setObjectName("AppSubtitle")
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(title)
        texts.addWidget(subtitle)
        layout.addWidget(icon)
        layout.addLayout(texts)
        if self.simulate:
            badge = QLabel("SIMULATION")
            badge.setObjectName("Badge")
            layout.addWidget(badge)
        layout.addSpacing(24)
        self.page_buttons = []
        for index, text in enumerate((tr("Measurement"), tr("Live"))):
            button = QToolButton()
            button.setObjectName("Segment")
            button.setText(text)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.clicked.connect(lambda _=False, i=index: self.show_page(i))
            layout.addWidget(button)
            self.page_buttons.append(button)
        layout.addStretch(1)
        self.language_combo = DataCombo()
        self.language_combo.setMinimumContentsLength(7)
        self.language_combo.set_items(list(LANGUAGES.items()), language())
        self.language_combo.setToolTip(tr("Language"))
        self.language_combo.currentIndexChanged.connect(self._language_selected)
        layout.addWidget(self.language_combo)
        help_button = QToolButton()
        help_button.setText(tr("? Help"))
        help_button.setToolTip(tr("Help on all functions (F1)"))
        help_button.clicked.connect(self.show_help)
        layout.addWidget(help_button)
        self.theme_button = QToolButton()
        self.theme_button.setToolTip(tr("Light/dark theme"))
        self.theme_button.clicked.connect(
            lambda: self.apply_theme("light" if self.theme == "dark" else "dark"))
        layout.addWidget(self.theme_button)
        return header

    def _build_sidebar(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        # devices
        card = Card(tr("Instruments"))
        self.device_list = QVBoxLayout()
        self.device_list.setSpacing(6)
        card.body.addLayout(self.device_list)
        self.no_devices = hint(tr("No instruments found yet. Switch the multimeter on, set its "
                                  "interface to RS-232 (9600 baud, even parity) and scan."))
        card.body.addWidget(self.no_devices)
        self.scan_button = QPushButton(tr("⟳  Scan for instruments"))
        self.scan_button.clicked.connect(self.scan_devices)
        self.all_ports = QCheckBox(tr("Also probe ports without a USB ID"))
        self.all_ports.setChecked(self.settings.value("scan/all_ports", False, type=bool))
        card.body.addWidget(self.scan_button)
        card.body.addWidget(self.all_ports)
        layout.addWidget(card)

        # test profile
        card = Card(tr("Test profile"))
        self.profile_combo = DataCombo()
        self.profile_label = muted(tr("Saves the measurement plan and the settings of every "
                                      "instrument under a name."))
        row = QHBoxLayout()
        self.profile_load = QPushButton(tr("Load"))
        self.profile_save = QPushButton(tr("Save …"))
        self.profile_delete = QToolButton()
        self.profile_delete.setText("🗑")
        self.profile_delete.setToolTip(tr("Delete the selected profile"))
        self.profile_folder = QToolButton()
        self.profile_folder.setText("📁")
        self.profile_folder.setToolTip(tr("Open the profile folder (profiles can be copied to "
                                          "other computers)"))
        row.addWidget(self.profile_load)
        row.addWidget(self.profile_save)
        row.addWidget(self.profile_delete)
        row.addWidget(self.profile_folder)
        card.body.addWidget(self.profile_combo)
        card.body.addLayout(row)
        card.body.addWidget(self.profile_label)
        layout.addWidget(card)
        self.profile_load.clicked.connect(self.load_selected_profile)
        self.profile_save.clicked.connect(self.save_profile_dialog)
        self.profile_delete.clicked.connect(self.delete_selected_profile)
        self.profile_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(profile_dir()))))
        self.profile_combo.currentIndexChanged.connect(self._profile_selection_changed)
        self.current_profile = ""
        self._refresh_profiles()

        # plan
        card = Card(tr("Measurement"))
        self.mode = DataCombo()
        self.mode.set_items([(MODE_SINGLE, tr("Continuous measurement")),
                             (MODE_LOOP, tr("Measurement series (loop): objects one after another"))],
                            self.settings.value("plan/mode", MODE_SINGLE))
        card.body.addWidget(FormRow(tr("Mode"), self.mode))
        card.body.addWidget(self._build_loop_editor())
        self.duration = TimeInput(DURATION_PRESETS, 60)
        self.interval = TimeInput(INTERVAL_PRESETS, 1)
        duration = self.settings.value("plan/duration", 60)
        self.duration.set_seconds(None if duration in (None, "", "None") else float(duration))
        self.interval.set_seconds(float(self.settings.value("plan/interval", 1)))
        self.duration_row = FormRow(tr("How long should it measure?"), self.duration)
        card.body.addWidget(self.duration_row)
        card.body.addWidget(FormRow(tr("Interval"), self.interval))
        card.body.addWidget(self._build_stability_editor())
        self.plan_info = muted("")
        card.body.addWidget(self.plan_info)
        self.note = QLineEdit()
        self.note.setPlaceholderText(tr("Note for the report (optional)"))
        card.body.addWidget(self.note)
        buttons = QHBoxLayout()
        self.start_button = QPushButton(tr("▶  Start measurement"))
        self.start_button.setObjectName("Primary")
        self.start_button.setMinimumHeight(40)
        self.stop_button = QPushButton(tr("■  Stop"))
        self.stop_button.setObjectName("Danger")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        buttons.addWidget(self.start_button, 2)
        buttons.addWidget(self.stop_button, 1)
        card.body.addLayout(buttons)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress_label = muted("")
        card.body.addWidget(self.progress)
        card.body.addWidget(self.progress_label)
        layout.addWidget(card)
        self.start_button.clicked.connect(self.start_measurement)
        self.stop_button.clicked.connect(self.stop_measurement)
        self.duration.changed.connect(self._update_plan_info)
        self.interval.changed.connect(self._update_plan_info)
        self.mode.currentIndexChanged.connect(self._mode_changed)

        # export
        card = Card(tr("Export"))
        self.csv_format = DataCombo()
        self.csv_format.set_items([(k, tr(v["label"])) for k, v in CSV_FORMATS.items()],
                                  self.settings.value("export/csv_format", "de"))
        card.body.addWidget(FormRow(tr("CSV format"), self.csv_format))
        row = QHBoxLayout()
        self.export_csv_button = QPushButton(tr("As CSV …"))
        self.export_txt_button = QPushButton(tr("As TXT …"))
        self.export_csv_button.clicked.connect(lambda: self.export("csv"))
        self.export_txt_button.clicked.connect(lambda: self.export("txt"))
        row.addWidget(self.export_csv_button)
        row.addWidget(self.export_txt_button)
        card.body.addLayout(row)
        self.export_png_button = QPushButton(tr("Chart as PNG …"))
        self.export_png_button.clicked.connect(self.export_chart)
        card.body.addWidget(self.export_png_button)
        autosave = QPushButton(tr("Open autosave folder"))
        autosave.setToolTip(str(autosave_dir()))
        autosave.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(autosave_dir()))))
        card.body.addWidget(autosave)
        card.body.addWidget(muted(tr("Every measurement is also saved continuously as CSV in the "
                                     "autosave folder.")))
        layout.addWidget(card)
        layout.addStretch(1)
        self._set_export_enabled(False)
        self.sidebar_scroll = scroll
        self._mode_changed()
        self._fit_sidebar()
        return scroll

    def _build_stability_editor(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.stability_on = QCheckBox(tr("Measure until stable"))
        self.stability_on.setChecked(self.settings.value("stability/on", False, type=bool))
        self.stability_window = QSpinBox()
        self.stability_window.setRange(2, 1000)
        self.stability_window.setValue(int(self.settings.value("stability/window", 10)))
        self.stability_limit = QDoubleSpinBox()
        self.stability_limit.setRange(0, 1e9)
        self.stability_limit.setDecimals(6)
        self.stability_limit.setValue(float(self.settings.value("stability/limit", 0.01)))
        self.stability_mode = DataCombo()
        self.stability_mode.set_items([(True, tr("% of the reading")),
                                       (False, tr("absolute (unit of the reading)"))],
                                      self.settings.value("stability/relative", True, type=bool))
        self.stability_details = QWidget()
        details = QVBoxLayout(self.stability_details)
        details.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(FormRow(tr("Last N readings"), self.stability_window))
        row.addWidget(FormRow(tr("Max. spread"), self.stability_limit))
        details.addLayout(row)
        details.addWidget(self.stability_mode)
        details.addWidget(muted(tr("Each instrument stops as soon as the spread (max − min) of "
                                   "its last N readings is within the limit. The duration above "
                                   "is the maximum time. The mean of these N readings is the "
                                   "final value.")))
        layout.addWidget(self.stability_on)
        layout.addWidget(self.stability_details)
        self.stability_on.toggled.connect(self._mode_changed)
        for widget in (self.stability_window, self.stability_limit):
            widget.valueChanged.connect(self._update_plan_info)
        self.stability_editor = box
        return box

    def _build_loop_editor(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(muted(tr("Objects measured one after another (e.g. the cores of a "
                                  "cable). Drag to reorder, double-click to rename.")))
        self.template = DataCombo()
        self.template.set_items([(None, tr("Insert template …"))] + [
            (i, f"{tr(name)}: {tr(items)}") for i, (name, items) in enumerate(LOOP_TEMPLATES)])
        self.template.currentIndexChanged.connect(self._apply_template)
        layout.addWidget(self.template)
        self.object_list = QListWidget()
        self.object_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.object_list.setMinimumHeight(150)
        self.object_list.setMaximumHeight(210)
        self.object_list.model().rowsMoved.connect(self._objects_changed)
        self.object_list.itemChanged.connect(self._objects_changed)
        layout.addWidget(self.object_list)
        row = QHBoxLayout()
        self.new_object = QLineEdit()
        self.new_object.setPlaceholderText(tr("New object, e.g. red"))
        self.new_object.returnPressed.connect(self._add_object)
        add = QPushButton("+")
        add.setFixedWidth(40)
        add.setToolTip(tr("Add (separate several with commas)"))
        add.clicked.connect(self._add_object)
        remove = QPushButton("−")
        remove.setFixedWidth(40)
        remove.setToolTip(tr("Remove selected object"))
        remove.clicked.connect(self._remove_object)
        clear = QPushButton(tr("Clear"))
        clear.clicked.connect(lambda: (self.object_list.clear(), self._objects_changed()))
        row.addWidget(self.new_object, 1)
        row.addWidget(add)
        row.addWidget(remove)
        row.addWidget(clear)
        layout.addLayout(row)
        self.advance = DataCombo()
        self.advance.set_items([(ADVANCE_CONFIRM, tr("After confirmation (button / Enter)")),
                                (ADVANCE_AUTO, tr("Automatically after a pause"))],
                               self.settings.value("loop/advance", ADVANCE_CONFIRM))
        self.pause = QDoubleSpinBox()
        self.pause.setRange(0, 3600)
        self.pause.setDecimals(1)
        self.pause.setSuffix(" s")
        self.pause.setValue(float(self.settings.value("loop/pause", 5)))
        self.pause_row = FormRow(tr("Pause for reconnecting"), self.pause)
        layout.addWidget(FormRow(tr("Next object"), self.advance))
        layout.addWidget(self.pause_row)
        self.advance.currentIndexChanged.connect(self._mode_changed)
        try:
            objects = json.loads(self.settings.value("loop/objects", "[]"))
        except (TypeError, ValueError):
            objects = []
        for name in objects:
            self._append_object(name)
        self.loop_editor = box
        return box

    def _build_settings_area(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(section_label(tr("Instrument settings")))
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setDocumentMode(True)
        self.settings_tabs.currentChanged.connect(self._tab_changed)
        self.settings_stack = QStackedWidget()
        self.settings_empty = hint(tr("Once instruments are found, their settings appear here."))
        self.settings_empty.setAlignment(Qt.AlignTop)
        self.settings_stack.addWidget(self.settings_empty)
        self.settings_stack.addWidget(self.settings_tabs)
        layout.addWidget(self.settings_stack, 1)
        box.setMinimumWidth(390)
        return box

    def _build_results_area(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(section_label(tr("Live readings")))

        # loop prompt banner
        self.banner = QFrame()
        self.banner.setObjectName("LoopBanner")
        banner_layout = QVBoxLayout(self.banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        self.banner_title = QLabel()
        self.banner_title.setObjectName("BannerTitle")
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        self.banner_text.setTextFormat(Qt.RichText)
        banner_layout.addWidget(self.banner_title)
        banner_layout.addWidget(self.banner_text)
        buttons = QHBoxLayout()
        self.measure_button = QPushButton(tr("▶  Measure"))
        self.measure_button.setObjectName("Primary")
        self.measure_button.setMinimumHeight(36)
        self.measure_button.setShortcut(QKeySequence(Qt.Key_Return))
        self.repeat_button = QPushButton(tr("↺  Repeat last step"))
        self.skip_button = QPushButton(tr("Skip"))
        self.end_loop_button = QPushButton(tr("End series"))
        self.end_loop_button.setObjectName("Danger")
        for button in (self.measure_button, self.repeat_button, self.skip_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.end_loop_button)
        banner_layout.addLayout(buttons)
        self.measure_button.clicked.connect(self._loop_measure_now)
        self.repeat_button.clicked.connect(self._loop_repeat)
        self.skip_button.clicked.connect(self._loop_skip)
        self.end_loop_button.clicked.connect(self._loop_end)
        self.banner.setVisible(False)
        layout.addWidget(self.banner)

        self.tiles_layout = QHBoxLayout()
        self.tiles_layout.setSpacing(10)
        self.tiles_placeholder = hint(tr("Start a measurement to see live values."))
        self.tiles_layout.addWidget(self.tiles_placeholder)
        layout.addLayout(self.tiles_layout)

        self.result_tabs = QTabWidget()
        self.result_tabs.setDocumentMode(True)
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.result_tabs.addTab(self.plot_widget, tr("Chart"))
        self.table_model = ReadingsModel()
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.result_tabs.addTab(self.table, tr("Table"))
        self.summary_table = QTableWidget(0, len(SUMMARY_HEADERS))
        self.summary_table.setHorizontalHeaderLabels([tr(h) for h in SUMMARY_HEADERS])
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.result_tabs.addTab(self.summary_table, tr("Overview"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.result_tabs.addTab(self.log, tr("Log"))
        layout.addWidget(self.result_tabs, 1)
        return box

    def _fit_sidebar(self):
        inner = self.sidebar_scroll.widget()
        inner.adjustSize()
        self.sidebar_scroll.setMinimumWidth(max(350, inner.minimumSizeHint().width() + 14))

    # ================================================================ theme / language / help
    def apply_theme(self, name: str):
        self.theme = name if name in THEMES else "dark"
        self.settings.setValue("ui/theme", self.theme)
        QApplication.instance().setStyleSheet(stylesheet(self.theme, checkmark_file(self.theme)))
        self.theme_button.setText("☀" if self.theme == "dark" else "☾")
        self.plot_widget.setBackground(THEMES[self.theme]["plot_bg"])
        for item in self._plot_items():
            self._style_plot(item)
        if hasattr(self, "live_page"):
            self.live_page.apply_theme(self.theme)

    def _plot_items(self):
        layout = self.plot_widget.ci
        return [layout.getItem(r, 0) for r in range(layout.layout.rowCount())
                if layout.getItem(r, 0) is not None]

    def _style_plot(self, item):
        colors = THEMES[self.theme]
        for axis in ("left", "bottom"):
            ax = item.getAxis(axis)
            ax.setPen(pg.mkPen(colors["grid"]))
            ax.setTextPen(pg.mkPen(colors["muted"]))
        item.showGrid(x=True, y=True, alpha=0.25)

    def _language_selected(self):
        code = self.language_combo.currentData()
        if code == language():
            return
        if self.busy():
            QMessageBox.information(self, APP_NAME, tr("The language can be changed after the "
                                                       "measurement."))
            self.language_combo.select_data(language())
            return
        self._store_settings()
        self.settings.setValue("ui/language", code)
        self.language_change_requested.emit(code)

    def show_help(self):
        HelpDialog(self).exec()

    # ================================================================ pages / live
    def show_page(self, index: int):
        for i, button in enumerate(self.page_buttons):
            button.setChecked(i == index)
        if index == self.pages.currentIndex():
            return
        if index == 1 and (self.session is not None or self.loop is not None):
            QMessageBox.information(self, APP_NAME, tr("Live mode is available after the "
                                                       "measurement."))
            self.page_buttons[0].setChecked(True)
            self.page_buttons[1].setChecked(False)
            return
        if index == 0 and self.live_page.running:
            if QMessageBox.question(self, APP_NAME, tr("Stop live mode?")) != QMessageBox.Yes:
                self.page_buttons[0].setChecked(False)
                self.page_buttons[1].setChecked(True)
                return
            self.live_page.shutdown()
        self.pages.setCurrentIndex(index)

    def _live_running_changed(self, running: bool):
        self._set_running(running)
        self.stop_button.setEnabled(False)

    def _live_record_ready(self, record):
        self.record = record
        self.table_model.reset()
        self.table_model.add(record.rows())
        self._update_summary()

    # ================================================================ logging
    def log_message(self, text: str, level: str = "info"):
        prefix = {"info": "", "warn": "⚠ ", "error": "✖ "}.get(level, "")
        self.log.appendPlainText(f"{datetime.now():%H:%M:%S}  {prefix}{text}")
        self.statusBar().showMessage(prefix + text, 8000)

    # ================================================================ devices
    def _run_task(self, fn, done, failed=None):
        task = Task(fn)
        self._tasks.add(task)

        def finish(ok, result):
            self._tasks.discard(task)
            (done if ok else (failed or (lambda e: self.log_message(e, "error"))))(result)

        task.signals.done.connect(lambda r: finish(True, r))
        task.signals.failed.connect(lambda e: finish(False, e))
        self.pool.start(task)

    def busy(self) -> bool:
        """True while a measurement, a series or live mode uses the instruments."""
        live = getattr(self, "live_page", None)
        return self.session is not None or self.loop is not None or (
            live is not None and live.running)

    def scan_devices(self):
        if self.busy():
            return
        self._store_configs()
        self.scan_button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.scan_button.setText(tr("Scanning …"))
        include_all = self.all_ports.isChecked()
        self.settings.setValue("scan/all_ports", include_all)
        self.log_message(tr("Scanning serial ports for HP 34401A …"))
        self._run_task(lambda: discover(include_all, self.simulate), self._devices_found,
                       self._scan_failed)

    def _scan_failed(self, error):
        self.scan_button.setEnabled(True)
        self.scan_button.setText(tr("⟳  Scan for instruments"))
        self.log_message(tr("Scan failed: {error}", error=error), "error")
        self._update_start_enabled()

    def _devices_found(self, devices: list[DeviceInfo]):
        self.scan_button.setEnabled(True)
        self.scan_button.setText(tr("⟳  Scan for instruments"))
        devices.sort(key=lambda d: (d.label, d.port))
        self.devices = devices
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows.clear()
        self.panels.clear()
        while self.settings_tabs.count():
            widget = self.settings_tabs.widget(0)
            self.settings_tabs.removeTab(0)
            widget.deleteLater()

        labels = [d.label for d in devices]
        loop = self.mode.currentData() == MODE_LOOP
        for index, info in enumerate(devices):
            color = DEVICE_COLORS[index % len(DEVICE_COLORS)]
            row = DeviceRow(info, color)
            row.selected.connect(self._select_device)
            row.advanced.connect(self.open_advanced)
            row.toggled.connect(self._update_start_enabled)
            row.toggled.connect(self._update_plan_info)
            self.device_list.addWidget(row)
            self.rows.append(row)
            panel = DeviceSettingsPanel(self._load_config(info))
            panel.set_loop_mode(loop)
            panel.changed.connect(self._update_plan_info)
            panel.apply_mode_requested.connect(lambda i=info: self.apply_mode(i))
            self.panels[info.port] = panel
            self.settings_tabs.addTab(panel, info.label)
            text = f"{info.label} – {info.port}"
            if info.usb_serial:
                text += f" (USB {info.usb_serial})"
            self.log_message(tr("Found: {device}", device=text))
            if not (info.calibration_message or "").strip():
                self.log_message(tr("{port}: no ID stored. Please assign a unique ID under ⚙.", port=info.port), "warn")
            if info.terminals.startswith("REAR"):
                self.log_message(tr("{device}: inputs switched to the REAR panel.",
                                    device=info.label), "warn")
        if len(set(labels)) != len(labels):
            self.log_message(tr("Several instruments have the same ID – to measure "
                                "simultaneously, please assign unique IDs under ⚙."), "warn")
        self.no_devices.setVisible(not devices)
        self.settings_stack.setCurrentIndex(1 if devices else 0)
        if not devices:
            self.log_message(tr("No HP 34401A found."), "warn")
        else:
            self.log_message(tr("{n} instrument(s) ready.", n=len(devices)))
        self._select_device(devices[0] if devices else None)
        self._fit_sidebar()
        self._update_start_enabled()
        self._update_plan_info()

    def _config_key(self, info: DeviceInfo) -> str:
        key = re.sub(r"[^A-Za-z0-9_.-]", "_", info.label.strip() or info.port)
        return f"devices/{key}"

    def _load_config(self, info: DeviceInfo) -> DeviceConfig:
        raw = self.settings.value(self._config_key(info))
        if raw:
            try:
                return DeviceConfig.from_dict(json.loads(raw))
            except (ValueError, TypeError):
                pass
        return DeviceConfig()

    def _store_configs(self):
        for info in self.devices:
            panel = self.panels.get(info.port)
            if panel is not None:
                self.settings.setValue(self._config_key(info), json.dumps(panel.config().to_dict()))

    def _store_settings(self):
        self._store_configs()
        plan = self._plan()
        self.settings.setValue("plan/duration", "None" if plan.duration is None else plan.duration)
        self.settings.setValue("plan/interval", plan.interval)
        self.settings.setValue("plan/mode", self.mode.currentData())
        self.settings.setValue("loop/objects", json.dumps(self._objects()))
        self.settings.setValue("loop/advance", self.advance.currentData())
        self.settings.setValue("loop/pause", self.pause.value())
        self.settings.setValue("export/csv_format", self.csv_format.currentData())
        self.settings.setValue("stability/on", self.stability_on.isChecked())
        self.settings.setValue("stability/window", self.stability_window.value())
        self.settings.setValue("stability/limit", self.stability_limit.value())
        self.settings.setValue("stability/relative", bool(self.stability_mode.currentData()))

    def _select_device(self, info):
        for index, row in enumerate(self.rows):
            row.set_selected(row.info is info)
            if row.info is info:
                self.settings_tabs.setCurrentIndex(index)

    def _tab_changed(self, index):
        for i, row in enumerate(self.rows):
            row.set_selected(i == index)

    def open_advanced(self, info: DeviceInfo):
        if self.busy():
            QMessageBox.information(self, APP_NAME, tr("Not available during a measurement."))
            return
        others = [d.label for d in self.devices if d is not info]
        old_key = self._config_key(info)
        config = self.panels[info.port].config() if info.port in self.panels else None
        dialog = AdvancedDialog(info, others, self)

        def id_changed(changed: DeviceInfo):
            if config is not None:
                self.settings.setValue(self._config_key(changed), json.dumps(config.to_dict()))
                self.settings.remove(old_key)
            for i, row in enumerate(self.rows):
                if row.info is changed:
                    row.refresh()
                    self.settings_tabs.setTabText(i, changed.label)
            self.log_message(tr("ID on {port} is now {id!r}.", port=changed.port,
                                id=changed.label))

        dialog.id_changed.connect(id_changed)
        dialog.exec()

    def apply_mode(self, info: DeviceInfo):
        if self.busy():
            return
        config = self.panels[info.port].config()
        problems = validate(config)
        if problems:
            QMessageBox.warning(self, APP_NAME, "\n".join(problems))
            return
        name = tr(config.func.label)
        self.log_message(tr("Switching {device} to \"{function}\" …", device=info.label,
                            function=name))
        self.panels[info.port].set_busy(True)

        def done(_):
            self.panels[info.port].set_busy(False)
            self.log_message(tr("{device} is in \"{function}\" mode – the front panel is active "
                                "again.", device=info.label, function=name))

        def failed(error):
            self.panels[info.port].set_busy(False)
            self.log_message(f"{info.label}: {error}", "error")
            QMessageBox.critical(self, APP_NAME, f"{info.label}: {error}")

        self._run_task(lambda: set_mode_only(info, config), done, failed)

    # ================================================================ loop editor
    def _objects(self) -> list[str]:
        return [self.object_list.item(i).text().strip() for i in range(self.object_list.count())
                if self.object_list.item(i).text().strip()]

    def _append_object(self, name: str):
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.object_list.addItem(item)

    def _add_object(self):
        for name in [n.strip() for n in self.new_object.text().split(",")]:
            if name:
                self._append_object(name)
        self.new_object.clear()
        self._objects_changed()

    def _remove_object(self):
        for item in self.object_list.selectedItems():
            self.object_list.takeItem(self.object_list.row(item))
        self._objects_changed()

    def _apply_template(self):
        index = self.template.currentData()
        if index is None:
            return
        self.object_list.clear()  # a template replaces the current list
        for name in tr(LOOP_TEMPLATES[index][1]).split(","):
            self._append_object(name.strip())
        self.template.setCurrentIndex(0)
        self._objects_changed()

    def _objects_changed(self, *args):
        self._update_plan_info()

    def _mode_changed(self):
        loop = self.mode.currentData() == MODE_LOOP
        self.loop_editor.setVisible(loop)
        self.pause_row.setVisible(self.advance.currentData() == ADVANCE_AUTO)
        stable = self.stability_on.isChecked()
        self.stability_details.setVisible(stable)
        if stable:
            self.duration_row.label.setText(tr("Maximum duration per object") if loop
                                            else tr("Maximum duration"))
        else:
            self.duration_row.label.setText(tr("Duration per object") if loop
                                            else tr("How long should it measure?"))
        for panel in self.panels.values():
            panel.set_loop_mode(loop)
        self._update_plan_info()

    # ================================================================ plan
    def _selected(self) -> list[tuple[DeviceInfo, DeviceConfig]]:
        return [(row.info, self.panels[row.info.port].config())
                for row in self.rows if row.use.isChecked()]

    def _stability(self) -> Stability | None:
        if not self.stability_on.isChecked():
            return None
        return Stability(self.stability_window.value(), self.stability_limit.value(),
                         bool(self.stability_mode.currentData()))

    def _plan(self) -> Plan:
        return Plan(interval=float(self.interval.seconds() or 0), duration=self.duration.seconds(),
                    stability=self._stability())

    def _update_start_enabled(self):
        idle = self.session is None and self.loop is None
        self.start_button.setEnabled(idle and any(row.use.isChecked() for row in self.rows))

    def _update_plan_info(self):
        if not hasattr(self, "plan_info"):
            return
        plan = self._plan()
        points = plan.expected_points()
        parts = []
        if plan.stability is not None:
            if plan.duration == 0:
                parts.append(tr("⚠ \"Until stable\" needs a maximum duration longer than 1 reading"))
            else:
                limit = (localize_number(f"{plan.stability.limit:g}")
                         + (" %" if plan.stability.relative else ""))
                parts.append(tr("until the last {n} readings are within {limit}",
                                n=plan.stability.window, limit=limit))
        elif plan.duration == 0:
            parts.append(tr("1 reading per instrument"))
        elif points is not None:
            parts.append(tr("{n} points per instrument", n=points))
        elif plan.duration is None:
            parts.append(tr("runs until stopped"))
        else:
            parts.append(tr("as many points as possible"))
        if self.mode.currentData() == MODE_LOOP:
            selected = sum(1 for row in self.rows if row.use.isChecked()) or 1
            objects = len(self._objects())
            steps = -(-objects // selected) if objects else 0
            parts.insert(0, tr("{objects} objects · {devices} instrument(s) → {steps} steps",
                               objects=objects, devices=selected, steps=steps))
            if plan.duration is None:
                parts.append(tr("⚠ Unlimited: every step runs until stopped"))
        slowest = max((estimated_reading_time(self.panels[r.info.port].config())
                       for r in self.rows if r.use.isChecked()), default=0)
        if plan.interval > 0 and slowest > plan.interval:
            parts.append(tr("⚠ one reading takes ≈ {s} s – longer than the interval",
                            s=localize_number(f"{slowest:.1f}")))
        self.plan_info.setText(" · ".join(parts))

    # ================================================================ measurement
    def start_measurement(self):
        selected = self._selected()
        if not selected or self.busy():
            return
        for info, config in selected:
            problems = validate(config)
            if problems:
                QMessageBox.warning(self, APP_NAME, f"{info.label}: " + " ".join(problems))
                return
        labels = [info.label for info, _ in selected]
        if len(set(labels)) != len(labels):
            QMessageBox.warning(self, APP_NAME, tr(
                "Two selected instruments have the same ID. Please assign unique IDs in the "
                "advanced settings."))
            return
        plan = self._plan()
        if plan.stability is not None and plan.duration == 0:
            QMessageBox.warning(self, APP_NAME, tr("\"Measure until stable\" needs a maximum "
                                                   "duration (not \"1 reading\")."))
            return
        loop = self.mode.currentData() == MODE_LOOP
        if loop:
            objects = self._objects()
            if not objects:
                QMessageBox.warning(self, APP_NAME, tr("The object list of the series is empty."))
                return
            steps = build_loop_steps(selected, objects)
        else:
            steps = [selected]
        self._store_settings()

        self.record = MeasurementRecord([], plan.interval, plan.duration,
                                        note=self.note.text().strip(), loop=loop,
                                        profile=self.current_profile, stability=plan.stability)
        self.record.devices = [DeviceRecord(i, c) for i, c in steps[0]]  # for the CSV columns
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        names = "_".join(re.sub(r"[^A-Za-z0-9_-]", "", i.label) or "dev" for i, _ in selected)
        try:
            self.writer = LiveCsvWriter(autosave_dir() / f"{stamp}_{names}.csv", self.record,
                                        self.csv_format.currentData())
        except OSError as error:
            self.writer = None
            self.log_message(tr("Autosave not possible: {error}", error=error), "warn")
        self.record.devices = []
        self._errors = []
        self.table_model.reset()
        self.summary_table.setRowCount(0)
        self._set_running(True)
        if loop:
            self.loop = LoopState(steps, self.advance.currentData(), self.pause.value())
            self.log_message(tr("Series with {n} steps started.", n=len(steps)))
            self._loop_prompt()
        else:
            self._run_step(steps[0], 1)

    def _run_step(self, assignments, step: int):
        plan = self._plan()
        session = Session(assignments, plan)
        self.slot_records = [DeviceRecord(info, config, step=step,
                                          stability_used=plan.stability is not None)
                             for info, config in assignments]
        self.record.devices.extend(self.slot_records)
        self._prepare_step(assignments)
        self.session = session
        for info, config in assignments:
            self.log_message(f"{info.label}: " + " · ".join(configuration_commands(config)))
        self.log_message(tr("Preparing measurement …"))
        self._start_time = None
        session.start()
        self.timer.start()
        self.plot_timer.start()
        self.stop_button.setEnabled(True)

    def stop_measurement(self):
        if self.session is not None:
            self.session.stop()
            self.stop_button.setEnabled(False)
            self.log_message(tr("Stop requested – finishing the current reading …"))
        elif self.loop is not None:
            self._loop_end()

    def _set_running(self, running: bool):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.scan_button.setEnabled(not running)
        for row in self.rows:
            row.use.setEnabled(not running)
        for panel in self.panels.values():
            panel.set_busy(running)
        for widget in (self.duration, self.interval, self.note, self.csv_format, self.mode,
                       self.loop_editor, self.language_combo, self.stability_editor,
                       self.profile_combo, self.profile_load, self.profile_save,
                       self.profile_delete):
            widget.setEnabled(not running)
        self._set_export_enabled(not running and self.record is not None and any(
            rec.readings for rec in self.record.devices))
        if not running:
            self._update_start_enabled()
            self._profile_selection_changed()

    def _set_export_enabled(self, enabled: bool):
        self.export_csv_button.setEnabled(enabled)
        self.export_txt_button.setEnabled(enabled)
        self.export_png_button.setEnabled(enabled)

    def _device_color(self, info: DeviceInfo) -> str:
        ports = [d.port for d in self.devices]
        index = ports.index(info.port) if info.port in ports else 0
        return DEVICE_COLORS[index % len(DEVICE_COLORS)]

    def _prepare_step(self, assignments):
        while self.tiles_layout.count():
            item = self.tiles_layout.takeAt(0)
            if item.widget() is not None and item.widget() is not self.tiles_placeholder:
                item.widget().deleteLater()
        self.tiles_placeholder.setVisible(False)
        self.tiles = []
        for info, config in assignments:
            tile = ReadoutTile(info, config, self._device_color(info))
            tile.set_status(tr("connecting …"))
            self.tiles.append(tile)
            self.tiles_layout.addWidget(tile, 1)

        self.plot_widget.clear()
        self.curves, self.avg_curves, self.plot_data = [], [], []
        first = None
        for slot, (info, config) in enumerate(assignments):
            color = self._device_color(info)
            item = self.plot_widget.addPlot(row=slot, col=0,
                                            axisItems={"bottom": ClockAxis(orientation="bottom")})
            self._style_plot(item)
            unit = config.unit
            title = f"{info.label} · {config.label}" if config.label else info.label
            if unit in ("dB", "dBm", ""):
                item.setLabel("left", f"{title} ({unit})" if unit else title)
            else:
                item.setLabel("left", title, units=unit)
            item.setLabel("bottom", tr("Time of day"))
            item.setClipToView(True)
            item.setDownsampling(auto=True, mode="peak")
            self._add_limit_lines(item, config)
            curve = item.plot([], [], pen=pg.mkPen(color, width=2), symbol="o", symbolSize=4,
                              symbolBrush=color, symbolPen=None)
            avg = None
            if config.moving_average > 1:
                avg = item.plot([], [], pen=pg.mkPen(THEMES[self.theme]["text"], width=1.5,
                                                     style=Qt.DashLine))
            if first is None:
                first = item
            else:
                item.setXLink(first)
            self.curves.append(curve)
            self.avg_curves.append(avg)
            self.plot_data.append(([], []))
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)

    def _add_limit_lines(self, item, config: DeviceConfig):
        """Draw limits in the plot when they refer to the measured value."""
        lines = []
        if config.math == MATH_LIMIT:
            lines = [config.limit_lower, config.limit_upper]
        elif config.conversion == CONV_NONE:
            if config.tolerance == TOL_PERCENT:
                d = abs(config.tol_nominal) * config.tol_value / 100
                lines = [config.tol_nominal - d, config.tol_nominal + d]
            elif config.tolerance == TOL_ABSOLUTE:
                lines = [config.tol_nominal - config.tol_value,
                         config.tol_nominal + config.tol_value]
            elif config.tolerance == TOL_RANGE:
                lines = [config.tol_low, config.tol_high]
        for value in lines:
            item.addLine(y=value, pen=pg.mkPen(THEMES[self.theme]["danger"], width=1,
                                               style=Qt.DotLine))

    def _poll_session(self):
        session = self.session
        if session is None:
            return
        new_rows = []
        for _ in range(2000):
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event, new_rows)
        if new_rows:
            self.table_model.add(new_rows)
            if self.result_tabs.currentWidget() is self.table:
                self.table.scrollToBottom()
        self._update_progress()
        if not session.running and session.events.empty():
            self._step_finished()

    def _handle_event(self, event, new_rows):
        slot = event.slot
        if event.kind == "started":
            self._start_time = time.monotonic()
            if self.record.started_at is None:
                self.record.started_at = self.session.started_at
            self.log_message(tr("Measurement running."))
            for tile in self.tiles:
                tile.set_status(tr("measuring"))
            return
        rec = self.slot_records[slot] if slot >= 0 else None
        name = rec.info.label if rec else ""
        tile = self.tiles[slot] if 0 <= slot < len(self.tiles) else None
        if event.kind == "reading":
            reading = event.reading
            rec.readings.append(reading)
            if self.writer is not None:
                try:
                    self.writer.add(rec, reading)
                except OSError as error:
                    self.log_message(tr("Autosave error: {error}", error=error), "warn")
                    self.writer = None
            new_rows.append((rec, reading))
            if reading.value is not None:
                xs, ys = self.plot_data[slot]
                xs.append(reading.timestamp.timestamp())
                ys.append(reading.value)
                self._plot_dirty = True
                panel = self.panels.get(rec.info.port)
                if panel is not None:
                    panel.set_last_value(reading.value)
            tile.show_reading(reading, rec.stats())
            if reading.status in ("TIMEOUT", "ERROR"):
                self.log_message(tr("{device}: measurement error ({status}) at point {point}",
                                    device=name, status=reading.status, point=reading.point),
                                 "warn")
        elif event.kind in ("status", "ready"):
            if event.data.get("instrument_minmax"):
                rec.instrument_minmax = event.data["instrument_minmax"]
            if tile and self._start_time is None:
                tile.set_status(event.text)
        elif event.kind == "warning":
            self.log_message(f"{name}: {event.text}", "warn")
        elif event.kind == "error":
            self._errors.append(f"{name}: {event.text}")
            self.log_message(f"{name}: {event.text}", "error")
            if tile:
                tile.set_status(tr("Error"))
        elif event.kind == "stable":
            rec.stable_value = event.data["value"]
            rec.stable_after = event.data["after"]
            if tile:
                tile.set_status(tr("stable ✓"))
            self.log_message(tr("{device}: stable after {s} s – final value {value}",
                                device=name, s=localize_number(f"{rec.stable_after:.1f}"),
                                value=format_reading(rec.config, rec.stable_value)))
        elif event.kind == "unstable":
            if tile:
                tile.set_status(tr("⚠ not stable"))
            self.log_message(tr("{device}: did not become stable within the maximum duration.",
                                device=name), "warn")
        elif event.kind == "finished":
            if tile and rec.stable_value is None and not rec.stability_used:
                tile.set_status(event.text)

    def _update_progress(self):
        if self._start_time is None:
            return
        elapsed = time.monotonic() - self._start_time
        plan = self.record
        count = sum(len(rec.readings) for rec in self.slot_records)
        if plan.duration:
            self.progress.setValue(int(min(1.0, elapsed / plan.duration) * 1000))
            text = f"{_hms(elapsed)} / {_hms(plan.duration)}"
        else:
            if plan.duration is None:
                self.progress.setRange(0, 0)
            text = _hms(elapsed)
        prefix = ""
        if self.loop is not None:
            prefix = tr("Step {i}/{n}", i=self.loop.index + 1, n=self.loop.total) + "  ·  "
        self.progress_label.setText(prefix + tr("{time}  ·  {n} readings", time=text, n=count))

    def _refresh_plot(self):
        if not self._plot_dirty:
            return
        self._plot_dirty = False
        for slot, (curve, (xs, ys)) in enumerate(zip(self.curves, self.plot_data)):
            curve.setData(xs, ys)
            curve.setSymbol("o" if len(xs) <= 500 else None)
            avg = self.avg_curves[slot]
            if avg is not None:
                avg.setData(xs, moving_average(ys, self.slot_records[slot].config.moving_average))

    def _step_finished(self):
        self.timer.stop()
        self.plot_timer.stop()
        self._plot_dirty = True
        self._refresh_plot()
        self.session = None
        self.progress.setRange(0, 1000)
        if self.record.duration is not None:
            self.progress.setValue(1000)
        self._update_summary()
        loop = self.loop
        if loop is not None and not loop.ending:
            loop.index += 1
            if loop.index < loop.total:
                self._show_errors()
                self._loop_prompt()
                return
        self._finish_all()

    def _show_errors(self):
        if self._errors:
            QMessageBox.warning(self, APP_NAME, tr("The measurement reported errors:") + "\n\n"
                                + "\n".join(self._errors))
            self._errors = []

    def _finish_all(self):
        self.loop = None
        self.banner.setVisible(False)
        self.countdown_timer.stop()
        self.record.finished_at = datetime.now().astimezone()
        if self.writer is not None:
            self.writer.close()
            self.log_message(tr("Autosave: {path}", path=self.writer.path))
            self.writer = None
        count = sum(len(rec.readings) for rec in self.record.devices)
        self.log_message(tr("Measurement finished – {n} readings. Export as .csv or .txt now.", n=count))
        self._set_running(False)
        if self.record.loop or len(self.record.devices) > 1:
            self.result_tabs.setCurrentWidget(self.summary_table)
        self._show_errors()

    # ================================================================ loop control
    def _loop_prompt(self):
        loop = self.loop
        step = loop.steps[loop.index]
        self.banner.setVisible(True)
        self.stop_button.setEnabled(True)
        self.banner_title.setText(tr("Step {i} of {n}", i=loop.index + 1, n=loop.total))
        lines = [f"<b>{info.label}</b>  →  <span style='font-size:14pt; font-weight:700'>"
                 f"{config.label}</span>" for info, config in step]
        self.banner_text.setText(tr("Please connect:") + "<br>" + "<br>".join(lines))
        self.repeat_button.setVisible(loop.index > 0)
        self.skip_button.setVisible(True)
        for button in (self.measure_button, self.repeat_button, self.skip_button):
            button.setEnabled(True)
        self.measure_button.setText(tr("▶  Measure"))
        if loop.advance == ADVANCE_AUTO and loop.index > 0:
            loop.countdown_end = time.monotonic() + loop.pause
            self.countdown_timer.start()
            self._countdown_tick()
        else:
            loop.countdown_end = None
            QApplication.beep()
        self.measure_button.setFocus()

    def _countdown_tick(self):
        loop = self.loop
        if loop is None or loop.countdown_end is None:
            self.countdown_timer.stop()
            return
        remaining = loop.countdown_end - time.monotonic()
        if remaining <= 0:
            self.countdown_timer.stop()
            self._loop_measure_now()
            return
        self.measure_button.setText(tr("▶  Measure now ({s} s)", s=int(remaining) + 1))

    def _loop_measure_now(self):
        loop = self.loop
        if loop is None or self.session is not None:
            return
        loop.countdown_end = None
        self.countdown_timer.stop()
        self.banner_title.setText(tr("Step {i} of {n} – measuring …", i=loop.index + 1,
                                     n=loop.total))
        self.measure_button.setEnabled(False)
        self.measure_button.setText(tr("measuring …"))
        self.repeat_button.setVisible(False)
        self.skip_button.setVisible(False)
        self._run_step(loop.steps[loop.index], loop.index + 1)

    def _loop_repeat(self):
        loop = self.loop
        if loop is None or self.session is not None or loop.index == 0:
            return
        loop.countdown_end = None
        self.countdown_timer.stop()
        loop.index -= 1
        step = loop.index + 1
        self.record.devices = [rec for rec in self.record.devices if rec.step != step]
        self.table_model.remove_step(step)
        self._update_summary()
        self.log_message(tr("Repeating step {i}.", i=step))
        self._loop_prompt()

    def _loop_skip(self):
        loop = self.loop
        if loop is None or self.session is not None:
            return
        loop.countdown_end = None
        self.countdown_timer.stop()
        names = ", ".join(config.label for _, config in loop.steps[loop.index])
        self.log_message(tr("Step {i} skipped ({names}).", i=loop.index + 1, names=names),
                         "warn")
        loop.index += 1
        if loop.index < loop.total:
            self._loop_prompt()
        else:
            self._finish_all()

    def _loop_end(self):
        if self.loop is None:
            return
        self.loop.ending = True
        self.log_message(tr("Series finished."))
        if self.session is not None:
            self.session.stop()  # _step_finished completes the series
            return
        self._finish_all()

    def _update_summary(self):
        if self.record is None:
            return
        rows = summary_rows(self.record)
        self.summary_table.setRowCount(len(rows))
        passed = tr("PASS")
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                item = QTableWidgetItem(text)
                if c in (3, 4, 5, 6, 7, 8, 9, 10):
                    item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                if c == len(row) - 1 and text:
                    item.setForeground(QColor("#34d399" if text.startswith(passed)
                                              else "#f87171"))
                self.summary_table.setItem(r, c, item)
        # Hide optional columns (calculated, final value, stable after) that are empty.
        for column in (8, 9, 10):
            self.summary_table.setColumnHidden(column, not any(row[column] for row in rows))

    # ================================================================ test profiles
    def _refresh_profiles(self, select: str = ""):
        profiles = list_profiles()
        self.profile_combo.set_items([(None, tr("Select a profile …"))] + [
            (str(path), name) for name, path in profiles])
        if select:
            for index in range(self.profile_combo.count()):
                if self.profile_combo.itemText(index) == select:
                    self.profile_combo.setCurrentIndex(index)
        self._profile_selection_changed()

    def _profile_selection_changed(self):
        selected = self.profile_combo.currentData() is not None
        idle = self.session is None and self.loop is None
        self.profile_load.setEnabled(selected and idle)
        self.profile_delete.setEnabled(selected and idle)

    def _profile_plan(self) -> dict:
        return {
            "mode": self.mode.currentData(),
            "duration": self.duration.seconds(),
            "interval": float(self.interval.seconds() or 0),
            "objects": self._objects(),
            "advance": self.advance.currentData(),
            "pause": self.pause.value(),
            "stability": {"on": self.stability_on.isChecked(),
                          "window": self.stability_window.value(),
                          "limit": self.stability_limit.value(),
                          "relative": bool(self.stability_mode.currentData())},
            "csv_format": self.csv_format.currentData(),
        }

    def save_profile_dialog(self):
        if not self.rows:
            QMessageBox.information(self, APP_NAME, tr("Scan for instruments first."))
            return
        name, ok = QInputDialog.getText(self, tr("Save test profile"), tr("Profile name:"),
                                        text=self.current_profile)
        name = name.strip()
        if not ok or not name:
            return
        if any(existing.lower() == name.lower() for existing, _ in list_profiles()):
            if QMessageBox.question(self, APP_NAME, tr("Overwrite the profile \"{name}\"?",
                                                       name=name)) != QMessageBox.Yes:
                return
        devices = [{"id": row.info.label, "use": row.use.isChecked(),
                    "config": self.panels[row.info.port].config().to_dict()} for row in self.rows]
        try:
            save_profile(name, self._profile_plan(), devices)
        except OSError as error:
            QMessageBox.critical(self, APP_NAME, str(error))
            return
        self.current_profile = name
        self._refresh_profiles(select=name)
        self._show_profile_state()
        self.log_message(tr("Test profile \"{name}\" saved.", name=name))

    def load_selected_profile(self):
        path = self.profile_combo.currentData()
        if path is None or self.session is not None or self.loop is not None:
            return
        try:
            profile = load_profile(Path(path))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, APP_NAME, tr("Profile could not be loaded: {error}",
                                                    error=error))
            return
        plan = profile["plan"]
        if plan.get("mode"):
            self.mode.select_data(plan["mode"])
        if "duration" in plan:
            self.duration.set_seconds(plan["duration"])
        if "interval" in plan:
            self.interval.set_seconds(plan["interval"])
        if isinstance(plan.get("objects"), list):
            self.object_list.clear()
            for name in plan["objects"]:
                self._append_object(str(name))
        if plan.get("advance"):
            self.advance.select_data(plan["advance"])
        if "pause" in plan:
            self.pause.setValue(float(plan["pause"]))
        stability = plan.get("stability") or {}
        if stability:
            self.stability_on.setChecked(bool(stability.get("on")))
            self.stability_window.setValue(int(stability.get("window", 10)))
            self.stability_limit.setValue(float(stability.get("limit", 0.01)))
            self.stability_mode.select_data(bool(stability.get("relative", True)))
        if plan.get("csv_format"):
            self.csv_format.select_data(plan["csv_format"])

        mapping = assign_configs(profile["devices"], [row.info.label for row in self.rows])
        for row in self.rows:
            entry = mapping.get(row.info.label)
            if entry is None:
                row.use.setChecked(False)
                continue
            self.panels[row.info.port].set_config(entry["config"])
            row.use.setChecked(entry["use"])
            source = entry["id"]
            if source and source != row.info.label:
                self.log_message(tr("Profile: settings of {source} applied to {device}.",
                                    source=source, device=row.info.label))
        if len(profile["devices"]) > len(self.rows):
            self.log_message(tr("Profile contains more instruments than are connected."), "warn")
        self.current_profile = str(profile.get("name", ""))
        self._mode_changed()
        self._show_profile_state()
        self.log_message(tr("Test profile \"{name}\" loaded.", name=self.current_profile))

    def delete_selected_profile(self):
        path = self.profile_combo.currentData()
        if path is None:
            return
        name = self.profile_combo.currentText()
        if QMessageBox.question(self, APP_NAME, tr("Delete the profile \"{name}\"?",
                                                   name=name)) != QMessageBox.Yes:
            return
        delete_profile(Path(path))
        if self.current_profile == name:
            self.current_profile = ""
        self._refresh_profiles()
        self._show_profile_state()
        self.log_message(tr("Test profile \"{name}\" deleted.", name=name))

    def _show_profile_state(self):
        if self.current_profile:
            self.profile_label.setText(tr("Active profile: <b>{name}</b>",
                                          name=self.current_profile))
        else:
            self.profile_label.setText(tr("Saves the measurement plan and the settings of every "
                                          "instrument under a name."))

    # ================================================================ export
    def export_chart(self, widget=None):
        widget = widget or self.plot_widget
        if widget is self.plot_widget and not self.curves:
            return
        started = self.record.started_at if self.record is not None else None
        stamp = (started or datetime.now()).strftime("%Y%m%d_%H%M%S")
        folder = self.settings.value("export/folder", str(Path.home()))
        suggestion = str(Path(folder) / f"HPMulti_{stamp}_chart.png")
        path, _ = QFileDialog.getSaveFileName(self, tr("Save chart"), suggestion,
                                              tr("PNG image (*.png)"))
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        # Render at twice the screen resolution for sharp images.
        ratio = 2.0
        image = QImage(int(widget.width() * ratio), int(widget.height() * ratio),
                       QImage.Format_ARGB32)
        image.fill(QColor(THEMES[self.theme]["plot_bg"]))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        widget.scene().render(painter, QRectF(image.rect()),
                              widget.mapToScene(widget.viewport().rect()).boundingRect())
        painter.end()
        if not image.save(path, "PNG"):
            QMessageBox.critical(self, APP_NAME, tr("Export failed: {error}", error=path))
            return
        self.settings.setValue("export/folder", str(Path(path).parent))
        self.log_message(tr("Exported: {path}", path=path))

    def export(self, kind: str):
        if self.record is None:
            return
        stamp = (self.record.started_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
        names = "-".join(dict.fromkeys(re.sub(r"[^A-Za-z0-9_-]", "", rec.info.label) or "dev"
                                       for rec in self.record.devices))
        folder = self.settings.value("export/folder", str(Path.home()))
        suggestion = str(Path(folder) / f"HPMulti_{stamp}_{names}.{kind}")
        filters = tr("CSV file (*.csv)") if kind == "csv" else tr("Text file (*.txt)")
        path, _ = QFileDialog.getSaveFileName(self, tr("Export readings"), suggestion,
                                              filters)
        if not path:
            return
        if not path.lower().endswith(f".{kind}"):
            path += f".{kind}"
        try:
            if kind == "csv":
                write_csv(self.record, Path(path), self.csv_format.currentData())
            else:
                write_txt(self.record, Path(path))
        except OSError as error:
            QMessageBox.critical(self, APP_NAME, tr("Export failed: {error}", error=error))
            return
        self.settings.setValue("export/folder", str(Path(path).parent))
        self.settings.setValue("export/csv_format", self.csv_format.currentData())
        self.log_message(tr("Exported: {path}", path=path))

    # ================================================================ close
    def shutdown(self) -> bool:
        """Stop running work and save settings. False if the user cancelled."""
        if self.live_page.running:
            if self.live_page.recording and QMessageBox.question(
                    self, APP_NAME, tr("A live recording is running. Stop it and quit?")) \
                    != QMessageBox.Yes:
                return False
            self.live_page.shutdown()
        if self.session is not None or self.loop is not None:
            if QMessageBox.question(self, APP_NAME, tr("A measurement is running. Stop and quit?")) != QMessageBox.Yes:
                return False
            if self.loop is not None:
                self.loop.ending = True
            if self.session is not None:
                self.session.stop()
                deadline = time.monotonic() + 15
                while self.session is not None and self.session.running \
                        and time.monotonic() < deadline:
                    QApplication.processEvents()
                    time.sleep(0.05)
                self._poll_session()
            if self.writer is not None:
                self.writer.close()
        self._store_settings()
        self.settings.setValue("ui/geometry", self.saveGeometry())
        return True

    def closeEvent(self, event):
        if not self.shutdown():
            event.ignore()
            return
        super().closeEvent(event)
