"""Live view: virtual front panel per instrument, rolling chart, recording on demand."""

from __future__ import annotations

import dataclasses
import queue
import re
import time
from collections import deque
from datetime import datetime

import pyqtgraph as pg
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from .. import APP_NAME
from ..acquisition import Reading
from ..analysis import statistics_of
from ..export import DeviceRecord, LiveCsvWriter, MeasurementRecord, status_text
from ..functions import (AC_RESOLUTIONS, AUTO, FUNCTIONS, GATE_TIMES, MATH_NONE, MATH_NULL,
                         DeviceConfig, digits_text, format_reading)
from ..i18n import N_, localize_number, tr
from ..instrument import DeviceInfo
from ..live import LiveSession
from ..paths import autosave_dir
from .device_panel import FUNCTION_ORDER
from .plotting import ClockAxis, apply_plot_theme, style_plot
from .widgets import DataCombo, hint, muted

LIVE_RATES = [(0, N_("As fast as possible")), (0.2, N_("0.2 s")), (0.5, N_("0.5 s")),
              (1, N_("1 s")), (2, N_("2 s")), (5, N_("5 s"))]
CHART_WINDOWS = [(60, N_("1 minute")), (300, N_("5 minutes")), (900, N_("15 minutes")),
                 (3600, N_("1 hour")), (None, N_("Everything"))]
# Front-panel DIGITS keys: 4½ slow, 5½ slow, 6½ fast (manual p. 54).
DC_DIGIT_KEYS = [("4S", 4), ("5S", 5), ("6F", 6)]
MAX_CHART_POINTS = 200_000


def _key(text: str, checkable: bool = True) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Key")
    button.setCheckable(checkable)
    button.setFocusPolicy(Qt.NoFocus)
    return button


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().deleteLater()


class LivePanel(QFrame):
    """Virtual front panel for one instrument."""

    config_changed = Signal(int, object)   # slot, DeviceConfig
    pause_toggled = Signal(int, bool)

    def __init__(self, slot: int, info: DeviceInfo, config: DeviceConfig, color: str):
        super().__init__()
        self.setObjectName("LivePanel")
        self.slot = slot
        self.info = info
        self.config = DeviceConfig.from_dict(config.to_dict())   # shown on the keys
        self.active = DeviceConfig.from_dict(config.to_dict())   # confirmed by the instrument
        self.values: list[float] = []
        self.times: list[float] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        name = QLabel(info.label)
        name.setObjectName("ReadoutName")
        name.setStyleSheet(f"color:{color};")
        top.addWidget(name)
        top.addWidget(muted(info.port, wrap=False))
        top.addStretch(1)
        self.status = muted("", wrap=False)
        top.addWidget(self.status)
        self.pause_button = _key(tr("⏸ Pause"))
        self.pause_button.toggled.connect(self._pause_toggled)
        top.addWidget(self.pause_button)
        layout.addLayout(top)

        display = QFrame()
        display.setObjectName("LiveDisplay")
        dlay = QVBoxLayout(display)
        dlay.setContentsMargins(16, 8, 16, 8)
        dlay.setSpacing(0)
        self.flags = QLabel()
        self.flags.setObjectName("LiveFlags")
        self.value = QLabel("—")
        self.value.setObjectName("LiveValue")
        self.value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value.setMinimumWidth(10)
        dlay.addWidget(self.flags)
        dlay.addWidget(self.value)
        layout.addWidget(display)

        stats = QHBoxLayout()
        self.stats = muted("", wrap=False)
        self.stats.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        reset = _key(tr("↺ Reset"), checkable=False)
        reset.setToolTip(tr("Reset min / max / average"))
        reset.clicked.connect(self.reset_stats)
        stats.addWidget(self.stats, 1)
        stats.addWidget(reset)
        layout.addLayout(stats)

        layout.addWidget(muted(tr("Function"), wrap=False))
        self.function_keys = QGridLayout()
        self.function_keys.setSpacing(4)
        self.function_group = QButtonGroup(self)
        for index, key in enumerate(FUNCTION_ORDER):
            button = _key(FUNCTIONS[key].short)
            button.setToolTip(tr(FUNCTIONS[key].label))
            self.function_group.addButton(button)
            button.clicked.connect(lambda _=False, k=key: self._set_function(k))
            self.function_keys.addWidget(button, index // 6, index % 6)
            button.setProperty("function", key)
        layout.addLayout(self.function_keys)

        self.range_label = muted(tr("Range"), wrap=False)
        layout.addWidget(self.range_label)
        self.range_keys = QHBoxLayout()
        self.range_keys.setSpacing(4)
        layout.addLayout(self.range_keys)

        self.digits_label = muted(tr("Resolution"), wrap=False)
        layout.addWidget(self.digits_label)
        self.digit_keys = QHBoxLayout()
        self.digit_keys.setSpacing(4)
        layout.addLayout(self.digit_keys)

        toggles = QHBoxLayout()
        toggles.setSpacing(4)
        self.null_key = _key(tr("Null"))
        self.null_key.setToolTip(tr("Null: the next reading becomes the offset and is subtracted "
                                    "from all further readings"))
        self.null_key.clicked.connect(self._toggle_null)
        self.autozero_key = _key(tr("Autozero"))
        self.autozero_key.clicked.connect(self._toggle_autozero)
        self.hiz_key = _key(tr("Hi-Z >10 GΩ"))
        self.hiz_key.setToolTip(tr("Input resistance >10 GΩ in the 100 mV … 10 V ranges"))
        self.hiz_key.clicked.connect(self._toggle_hiz)
        for button in (self.null_key, self.autozero_key, self.hiz_key):
            toggles.addWidget(button)
        toggles.addStretch(1)
        layout.addLayout(toggles)
        layout.addStretch(1)
        self.set_config(self.config)

    # ------------------------------------------------------------------ state
    def confirm_config(self, config: DeviceConfig):
        """The instrument now measures with ``config``: readings and statistics follow it."""
        changed = config.to_dict() != self.active.to_dict()
        self.active = DeviceConfig.from_dict(config.to_dict())
        self.set_config(config)
        if changed:
            self.reset_stats()
            self.value.setText("…")

    def set_config(self, config: DeviceConfig):
        """Show a configuration on the keys without emitting signals."""
        self.config = DeviceConfig.from_dict(config.to_dict())
        func = config.func
        for button in self.function_group.buttons():
            button.setChecked(button.property("function") == config.function)

        _clear_layout(self.range_keys)
        fixed = func.kind == "fixed"
        self.range_label.setVisible(not fixed)
        if not fixed:
            items = [(AUTO, tr("Auto"))] + [(value, label) for label, value in func.ranges]
            group = QButtonGroup(self)
            for value, text in items:
                button = _key(text)
                button.setChecked(config.range == value)
                group.addButton(button)
                button.clicked.connect(lambda _=False, v=value: self._set_range(v))
                self.range_keys.addWidget(button)
            self.range_keys.addStretch(1)

        _clear_layout(self.digit_keys)
        self.digits_label.setVisible(not fixed)
        if not fixed:
            group = QButtonGroup(self)
            if func.kind == "dc":
                keys = [(key, digits_text(d), config.digits == d) for key, d in DC_DIGIT_KEYS]
            elif func.kind == "ac":
                keys = [(key, digits_text(d), config.ac_resolution == key)
                        for key, _, d in AC_RESOLUTIONS]
            else:
                keys = [(gate, f"{label} · {digits_text(d)}", config.gate_time == gate)
                        for gate, label, d in GATE_TIMES]
            for key, text, checked in keys:
                button = _key(text)
                button.setChecked(checked)
                group.addButton(button)
                button.clicked.connect(lambda _=False, k=key: self._set_resolution(k))
                self.digit_keys.addWidget(button)
            self.digit_keys.addStretch(1)

        self.null_key.setVisible(MATH_NULL in func.math)
        self.null_key.setChecked(config.math == MATH_NULL)
        self.autozero_key.setVisible(func.autozero)
        self.autozero_key.setChecked(config.autozero != "OFF")
        self.hiz_key.setVisible(func.impedance)
        self.hiz_key.setChecked(config.high_impedance)
        self._update_flags()

    def _update_flags(self, pending: bool = False):
        cfg = self.config
        func = cfg.func
        parts = [func.short]
        if func.kind != "fixed":
            parts.append(tr("AUTO") if cfg.range == AUTO else cfg.range_label())
            parts.append(digits_text(cfg.digits))
            if func.kind == "dc":
                parts.append(f"{localize_number(f'{cfg.nplc:g}')} NPLC")
        if func.autozero and cfg.autozero == "OFF":
            parts.append(tr("AZ OFF"))
        if cfg.math == MATH_NULL:
            parts.append(tr("NULL"))
        elif cfg.math != MATH_NONE:
            parts.append(cfg.math)
        if func.impedance and cfg.high_impedance:
            parts.append("HI-Z")
        if pending:
            parts.append("…")
        self.flags.setText("  ·  ".join(parts))

    def _changed(self, config: DeviceConfig):
        self.set_config(config)
        self._update_flags(pending=True)
        self.config_changed.emit(self.slot, DeviceConfig.from_dict(config.to_dict()))

    def _copy(self) -> DeviceConfig:
        return DeviceConfig.from_dict(self.config.to_dict())

    # ------------------------------------------------------------------ keys
    def _set_function(self, key: str):
        if key == self.config.function:
            return
        config = self._copy()
        config.function = key
        config.range = AUTO
        if config.math not in config.func.math:
            config.math = MATH_NONE
        self._changed(config)

    def _set_range(self, value):
        config = self._copy()
        config.range = value
        self._changed(config)

    def _set_resolution(self, key):
        config = self._copy()
        kind = config.func.kind
        if kind == "dc":
            config.dc_resolution = key
        elif kind == "ac":
            config.ac_resolution = key
        else:
            config.gate_time = key
        self._changed(config)

    def _toggle_null(self, checked: bool):
        config = self._copy()
        config.math = MATH_NULL if checked else MATH_NONE
        config.null_offset = None  # the next reading becomes the offset
        self._changed(config)

    def _toggle_autozero(self, checked: bool):
        config = self._copy()
        config.autozero = "ON" if checked else "OFF"
        self._changed(config)

    def _toggle_hiz(self, checked: bool):
        config = self._copy()
        config.high_impedance = checked
        self._changed(config)

    def _pause_toggled(self, paused: bool):
        self.pause_button.setText(tr("▶ Continue") if paused else tr("⏸ Pause"))
        self.pause_toggled.emit(self.slot, paused)

    # ------------------------------------------------------------------ readings
    def show_reading(self, reading: Reading):
        if reading.value is None:
            self.value.setText(status_text(reading.status))
        else:
            self.value.setText(format_reading(self.active, reading.value))
            self.values.append(reading.value)
            self.times.append(reading.elapsed)
        stats = statistics_of(self.values)
        if stats["count"]:
            def fmt(v):
                return format_reading(self.active, v)
            self.stats.setText(f"MIN {fmt(stats['min'])}   MAX {fmt(stats['max'])}   "
                               f"Ø {fmt(stats['mean'])}   n = {stats['count']}")

    def reset_stats(self):
        self.values.clear()
        self.times.clear()
        self.stats.setText("")

    def set_status(self, text: str):
        self.status.setText(text)

    def set_controls_enabled(self, enabled: bool):
        for layout in (self.function_keys, self.range_keys, self.digit_keys):
            for index in range(layout.count()):
                widget = layout.itemAt(index).widget()
                if widget is not None:
                    widget.setEnabled(enabled)
        for button in (self.null_key, self.autozero_key, self.hiz_key, self.pause_button):
            button.setEnabled(enabled)


class LivePage(QWidget):
    """Live mode: connect, read continuously, change settings, record on demand."""

    running_changed = Signal(bool)
    record_ready = Signal(object)   # MeasurementRecord after recording

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.session: LiveSession | None = None
        self.panels: list[LivePanel] = []
        self.curves = []
        self.data: list[tuple[deque, deque]] = []
        self.record: MeasurementRecord | None = None
        self.record_slots: list[DeviceRecord | None] = []
        self.record_t0 = 0.0
        self.writer: LiveCsvWriter | None = None
        self._errors: list[str] = []
        self._dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        bar = QFrame()
        bar.setObjectName("Card")
        blay = QHBoxLayout(bar)
        blay.setContentsMargins(14, 10, 14, 10)
        self.start_button = QPushButton(tr("▶  Start live"))
        self.start_button.setObjectName("Primary")
        self.start_button.setMinimumHeight(36)
        self.start_button.clicked.connect(self.toggle_live)
        self.rate = DataCombo()
        self.rate.set_items([(v, tr(t)) for v, t in LIVE_RATES],
                            float(main.settings.value("live/rate", 0.5)))
        self.rate.currentIndexChanged.connect(self._rate_changed)
        self.record_button = QPushButton(tr("●  Record"))
        self.record_button.setObjectName("Danger")
        self.record_button.setMinimumHeight(36)
        self.record_button.setEnabled(False)
        self.record_button.clicked.connect(self.toggle_record)
        self.record_label = QLabel("")
        self.record_label.setObjectName("RecordLabel")
        self.window = DataCombo()
        self.window.set_items([(v, tr(t)) for v, t in CHART_WINDOWS], 300)
        self.window.currentIndexChanged.connect(lambda: self._set_dirty())
        self.png_button = QPushButton(tr("Chart as PNG …"))
        self.png_button.setEnabled(False)
        self.png_button.clicked.connect(lambda: main.export_chart(self.plot_widget))
        blay.addWidget(self.start_button)
        blay.addWidget(muted(tr("Read rate"), wrap=False))
        blay.addWidget(self.rate)
        blay.addSpacing(16)
        blay.addWidget(self.record_button)
        blay.addWidget(self.record_label, 1)
        blay.addWidget(muted(tr("Chart"), wrap=False))
        blay.addWidget(self.window)
        blay.addWidget(self.png_button)
        root.addWidget(bar)

        self.placeholder = hint(tr(
            "Live mode keeps the ticked instruments connected and shows their readings "
            "continuously. Change function, range and resolution with the keys – like on the "
            "front panel. Press Record at any time to log the readings; afterwards export them "
            "under Measurement › Export or as PNG here. Changes are taken over into the "
            "instrument settings."))
        root.addWidget(self.placeholder)
        self.panel_row = QHBoxLayout()
        self.panel_row.setSpacing(12)
        root.addLayout(self.panel_row)
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setMinimumHeight(220)
        root.addWidget(self.plot_widget, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._poll)
        self.plot_timer = QTimer(self)
        self.plot_timer.setInterval(400)
        self.plot_timer.timeout.connect(self._refresh_plot)
        self.apply_theme(main.theme)

    # ------------------------------------------------------------------ helpers
    @property
    def running(self) -> bool:
        return self.session is not None

    @property
    def recording(self) -> bool:
        return self.record is not None and self.record.finished_at is None

    def apply_theme(self, theme: str):
        apply_plot_theme(self.plot_widget, theme)

    def _set_dirty(self):
        self._dirty = True
        self._refresh_plot()

    # ------------------------------------------------------------------ start / stop
    def toggle_live(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.running or self.main.busy():
            return
        selected = self.main.selected_devices()
        if not selected:
            QMessageBox.information(self, APP_NAME, tr("Tick at least one instrument under "
                                                       "Measurement › Instruments."))
            return
        try:
            session = LiveSession(selected, float(self.rate.currentData() or 0))
        except ValueError as error:
            QMessageBox.warning(self, APP_NAME, str(error))
            return
        self.main.store_configs()
        self._errors = []
        self._build_panels(selected)
        self.session = session
        session.start()
        self.timer.start()
        self.plot_timer.start()
        self.start_button.setText(tr("■  Stop live"))
        self.start_button.setObjectName("Danger")
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)
        self.record_button.setEnabled(True)
        self.placeholder.setVisible(False)
        self.main.log_message(tr("Live mode started."))
        self.running_changed.emit(True)

    def stop(self):
        if not self.running:
            return
        if self.recording:
            self.toggle_record()
        self.session.stop()
        self.start_button.setEnabled(False)
        self.start_button.setText(tr("Stopping …"))

    def _finished(self):
        self.timer.stop()
        self.plot_timer.stop()
        self._refresh_plot()
        self.session = None
        for panel in self.panels:
            panel.set_controls_enabled(False)
        self.start_button.setEnabled(True)
        self.start_button.setText(tr("▶  Start live"))
        self.start_button.setObjectName("Primary")
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)
        self.record_button.setEnabled(False)
        self.main.log_message(tr("Live mode stopped – the instruments are back in local mode."))
        self.running_changed.emit(False)
        if self._errors:
            QMessageBox.warning(self, APP_NAME, "\n".join(self._errors))
            self._errors = []

    def _build_panels(self, selected):
        _clear_layout(self.panel_row)
        self.panels = []
        self.plot_widget.clear()
        self.curves, self.data = [], []
        first = None
        for slot, (info, config) in enumerate(selected):
            color = self.main.device_color(info)
            panel = LivePanel(slot, info, config, color)
            panel.config_changed.connect(self._config_changed)
            panel.pause_toggled.connect(self._pause_toggled)
            self.panels.append(panel)
            self.panel_row.addWidget(panel, 1)
            item = self.plot_widget.addPlot(row=slot, col=0,
                                            axisItems={"bottom": ClockAxis(orientation="bottom")})
            style_plot(item, self.main.theme)
            item.setLabel("bottom", tr("Time of day"))
            item.setClipToView(True)
            item.setDownsampling(auto=True, mode="peak")
            item.showGrid(x=True, y=True, alpha=0.25)
            curve = item.plot([], [], pen=pg.mkPen(color, width=2))
            if first is None:
                first = item
            else:
                item.setXLink(first)
            self.curves.append((item, curve))
            self.data.append((deque(maxlen=MAX_CHART_POINTS), deque(maxlen=MAX_CHART_POINTS)))
            self._label_plot(slot, config)

    def _label_plot(self, slot: int, config: DeviceConfig):
        item, _ = self.curves[slot]
        title = self.panels[slot].info.label
        if config.unit in ("dB", "dBm", ""):
            item.setLabel("left", f"{title} ({config.unit})" if config.unit else title)
        else:
            item.setLabel("left", title, units=config.unit)

    # ------------------------------------------------------------------ commands
    def _config_changed(self, slot: int, config: DeviceConfig):
        if self.session is not None:
            self.session.devices[slot].set_config(config)

    def _pause_toggled(self, slot: int, paused: bool):
        if self.session is not None:
            self.session.devices[slot].set_paused(paused)

    def _rate_changed(self):
        rate = float(self.rate.currentData() or 0)
        self.main.settings.setValue("live/rate", rate)
        if self.session is not None:
            self.session.set_interval(rate)

    # ------------------------------------------------------------------ events
    def _poll(self):
        session = self.session
        if session is None:
            return
        for _ in range(2000):
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                break
            self._handle(event)
        if self.recording:
            self._update_record_label()
        if not session.running and session.events.empty():
            self._finished()

    def _handle(self, event):
        slot = event.slot
        panel = self.panels[slot] if 0 <= slot < len(self.panels) else None
        if panel is None:
            return
        name = panel.info.label
        if event.kind == "reading":
            reading = event.reading
            panel.show_reading(reading)
            if reading.value is not None:
                xs, ys = self.data[slot]
                xs.append(reading.timestamp.timestamp())
                ys.append(reading.value)
                self._dirty = True
                settings_panel = self.main.panels.get(panel.info.port)
                if settings_panel is not None:
                    settings_panel.set_last_value(reading.value)
            if self.recording:
                self._record(slot, reading)
        elif event.kind == "configured":
            config = event.data["config"]
            if (config.function, config.unit) != (panel.active.function, panel.active.unit):
                xs, ys = self.data[slot]  # different quantity: start a fresh curve
                xs.clear()
                ys.clear()
                self._dirty = True
            panel.confirm_config(config)
            panel.set_status(tr("live"))
            self._label_plot(slot, config)
            self._sync_settings(panel.info, config)
            if self.recording and self.record_slots[slot] is not None and \
                    self.record_slots[slot].config.to_dict() != config.to_dict():
                self._new_segment(slot, config)
        elif event.kind == "paused":
            panel.set_status(tr("paused"))
        elif event.kind == "resumed":
            panel.set_status(tr("live"))
        elif event.kind == "status":
            panel.set_status(event.text)
        elif event.kind == "warning":
            self.main.log_message(f"{name}: {event.text}", "warn")
            QMessageBox.warning(self, APP_NAME, f"{name}: {event.text}")
        elif event.kind == "error":
            self._errors.append(f"{name}: {event.text}")
            self.main.log_message(f"{name}: {event.text}", "error")
            panel.set_status(tr("Error"))
        elif event.kind == "finished":
            panel.set_status(event.text)

    def _sync_settings(self, info: DeviceInfo, config: DeviceConfig):
        """Take a live change over into the instrument's settings tab."""
        settings_panel = self.main.panels.get(info.port)
        if settings_panel is None:
            return
        merged = DeviceConfig.from_dict(config.to_dict())
        merged.label = settings_panel.config().label
        settings_panel.set_config(merged)

    def _refresh_plot(self):
        if not self._dirty:
            return
        self._dirty = False
        window = self.window.currentData()
        now = time.time()
        for (item, curve), (xs, ys) in zip(self.curves, self.data):
            if window is None:
                curve.setData(list(xs), list(ys))
            else:
                start = now - window
                pairs = [(x, y) for x, y in zip(xs, ys) if x >= start]
                curve.setData([p[0] for p in pairs], [p[1] for p in pairs])
                if pairs:
                    item.setXRange(max(start, pairs[0][0]), max(now, pairs[0][0] + 5),
                                   padding=0.02)

    # ------------------------------------------------------------------ recording
    def toggle_record(self):
        if self.recording:
            self.record.finished_at = datetime.now().astimezone()
            if self.writer is not None:
                self.writer.close()
                self.main.log_message(tr("Autosave: {path}", path=self.writer.path))
                self.writer = None
            count = sum(len(rec.readings) for rec in self.record.devices)
            self.main.log_message(tr("Recording stopped – {n} readings.", n=count))
            self.record_button.setText(tr("●  Record"))
            self.record_label.setText(tr("Recorded: {n} readings – export under Measurement "
                                         "› Export", n=count))
            self.png_button.setEnabled(True)
            self.record_ready.emit(self.record)
            return
        if not self.running:
            return
        self.record = MeasurementRecord([], float(self.rate.currentData() or 0), None,
                                        started_at=datetime.now().astimezone(),
                                        note=tr("Live recording"),
                                        profile=self.main.current_profile)
        self.record_t0 = time.monotonic() - self.session.t0
        self.record_slots = [None] * len(self.panels)
        self.record.devices = [DeviceRecord(p.info, p.active) for p in self.panels]
        names = "_".join(re.sub(r"[^A-Za-z0-9_-]", "", p.info.label) or "dev"
                         for p in self.panels)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            self.writer = LiveCsvWriter(autosave_dir() / f"{stamp}_live_{names}.csv", self.record,
                                        self.main.csv_format)
        except OSError as error:
            self.writer = None
            self.main.log_message(tr("Autosave not possible: {error}", error=error), "warn")
        self.record.devices = []
        for slot, panel in enumerate(self.panels):
            self._new_segment(slot, panel.active)
        self.record_button.setText(tr("■  Stop recording"))
        self.png_button.setEnabled(True)
        self.main.log_message(tr("Recording started."))

    def _new_segment(self, slot: int, config: DeviceConfig):
        """Start a new record section for an instrument (at start and after a change)."""
        current = self.record_slots[slot]
        if current is not None and not current.readings:
            self.record.devices.remove(current)
        segment = DeviceRecord(self.panels[slot].info, DeviceConfig.from_dict(config.to_dict()))
        self.record.devices.append(segment)
        self.record_slots[slot] = segment

    def _record(self, slot: int, reading: Reading):
        segment = self.record_slots[slot]
        if segment is None:
            return
        shifted = dataclasses.replace(reading, elapsed=reading.elapsed - self.record_t0,
                                      point=len(segment.readings))
        segment.readings.append(shifted)
        if self.writer is not None:
            try:
                self.writer.add(segment, shifted)
            except OSError as error:
                self.main.log_message(tr("Autosave error: {error}", error=error), "warn")
                self.writer = None

    def _update_record_label(self):
        seconds = int((datetime.now().astimezone() - self.record.started_at).total_seconds())
        count = sum(len(rec.readings) for rec in self.record.devices)
        self.record_label.setText(tr("● REC {time}  ·  {n} readings",
                                     time=f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:"
                                          f"{seconds % 60:02d}", n=count))

    def shutdown(self, timeout: float = 10.0):
        """Stop live mode synchronously (used when closing or switching pages)."""
        if not self.running:
            return
        from PySide6.QtWidgets import QApplication
        self.stop()
        deadline = time.monotonic() + timeout
        while self.session is not None and time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(0.05)
            self._poll()

