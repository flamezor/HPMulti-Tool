"""Main window of HPMulti-Tool.

The window assembles the parts and connects them:

- ``HeaderBar``           title, page switch, language, help, theme
- sidebar cards           instruments, test profile, measurement plan, export
- settings tabs           one ``DeviceSettingsPanel`` per instrument
- ``ResultsView``         banner, readout tiles, chart, table, overview, log
- ``MeasurementRunner``   runs a measurement or series
- ``LivePage``            live mode

It also owns what concerns several parts: the detected instruments and their
stored settings, loading/saving profiles and exporting.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QThreadPool, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QMainWindow, QMessageBox, QScrollArea,
                               QSplitter, QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from .. import APP_NAME
from ..acquisition import set_mode_only
from ..export import DeviceRecord, LiveCsvWriter, MeasurementRecord, write_csv, write_txt
from ..functions import DeviceConfig, is_loggable, not_loggable_text, validate
from ..i18n import language, tr
from ..instrument import DeviceInfo, discover
from ..paths import autosave_dir
from ..profiles import assign_configs, save_profile
from ..series import LoopState, build_loop_steps
from .advanced_dialog import AdvancedDialog
from .device_list import DeviceRow
from .device_panel import DeviceSettingsPanel
from .header import PAGE_LIVE, PAGE_MEASUREMENT, HeaderBar
from .help_dialog import HelpDialog
from .icon import app_icon
from .live_page import LivePage
from .measurement_runner import MeasurementRunner
from .plan_card import PlanCard
from .plotting import render_png
from .results_view import ResultsView
from .sidebar_cards import DevicesCard, ExportCard, ProfileCard
from .style import DEVICE_COLORS, THEMES, checkmark_file, stylesheet
from .widgets import Task, hint, section_label

LOG_PREFIX = {"info": "", "warn": "⚠ ", "error": "✖ "}


def safe_name(text: str) -> str:
    """Characters allowed in a file name part."""
    return re.sub(r"[^A-Za-z0-9_-]", "", text)


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
        self.panels: dict[str, DeviceSettingsPanel] = {}

        self.setWindowTitle(f"{APP_NAME}  –  HP 34401A" + ("  [Simulation]" if simulate else ""))
        self.setWindowIcon(app_icon())
        self.resize(1600, 960)
        self._build()
        self.apply_theme(self.theme)
        geometry = self.settings.value("ui/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
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
        self.header = HeaderBar(self.simulate)
        self.header.page_requested.connect(self.show_page)
        self.header.language_selected.connect(self._language_selected)
        self.header.theme_toggled.connect(
            lambda: self.apply_theme("light" if self.theme == "dark" else "dark"))
        self.header.help_requested.connect(self.show_help)
        root.addWidget(self.header)

        self.results = ResultsView(self.theme)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_settings_area())
        splitter.addWidget(self.results)
        splitter.setSizes([390, 440, 770])
        splitter.setStretchFactor(2, 1)
        wrapper = QWidget()
        lay = QVBoxLayout(wrapper)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(splitter)

        self.runner = MeasurementRunner(self.plan_card, self.results, self.device_color, self)
        self.runner.message.connect(self.log_message)
        self.runner.running_changed.connect(self._set_running)
        self.runner.value_received.connect(self._show_last_value)
        self.plan_card.stop_requested.connect(self.runner.stop)

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

    def _build_sidebar(self):
        self.devices_card = DevicesCard(self.settings)
        self.devices_card.scan_requested.connect(self.scan_devices)

        self.profile_card = ProfileCard()
        self.profile_card.save_requested.connect(self.save_profile)
        self.profile_card.load_requested.connect(self.apply_profile)
        self.profile_card.message.connect(self.log_message)

        self.plan_card = PlanCard(self.settings)
        self.plan_card.changed.connect(self._update_plan_info)
        self.plan_card.mode_changed.connect(self._loop_mode_changed)
        self.plan_card.start_requested.connect(self.start_measurement)

        self.export_card = ExportCard(self.settings)
        self.export_card.export_requested.connect(self.export)
        self.export_card.chart_requested.connect(self.export_chart)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)
        for card in (self.devices_card, self.profile_card, self.plan_card, self.export_card):
            layout.addWidget(card)
        layout.addStretch(1)
        self.sidebar_scroll = scroll
        self._fit_sidebar()
        return scroll

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
        empty = hint(tr("Once instruments are found, their settings appear here."))
        empty.setAlignment(Qt.AlignTop)
        self.settings_stack.addWidget(empty)
        self.settings_stack.addWidget(self.settings_tabs)
        layout.addWidget(self.settings_stack, 1)
        box.setMinimumWidth(390)
        return box

    def _fit_sidebar(self):
        inner = self.sidebar_scroll.widget()
        inner.adjustSize()
        self.sidebar_scroll.setMinimumWidth(max(350, inner.minimumSizeHint().width() + 14))

    # ================================================================ interface for LivePage
    @property
    def rows(self) -> list[DeviceRow]:
        return self.devices_card.rows

    @property
    def csv_format(self) -> str:
        return self.export_card.csv_format

    @property
    def current_profile(self) -> str:
        return self.profile_card.current

    def busy(self) -> bool:
        """True while a measurement, a series or live mode uses the instruments."""
        live = getattr(self, "live_page", None)
        return self.runner.busy or (live is not None and live.running)

    def selected_devices(self) -> list[tuple[DeviceInfo, DeviceConfig]]:
        return [(row.info, self.panels[row.info.port].config())
                for row in self.devices_card.checked_rows()]

    def device_color(self, info: DeviceInfo) -> str:
        ports = [d.port for d in self.devices]
        index = ports.index(info.port) if info.port in ports else 0
        return DEVICE_COLORS[index % len(DEVICE_COLORS)]

    def log_message(self, text: str, level: str = "info"):
        prefix = LOG_PREFIX.get(level, "")
        self.results.append_log(f"{datetime.now():%H:%M:%S}  {prefix}{text}")
        self.statusBar().showMessage(prefix + text, 8000)

    # ================================================================ theme / language / help
    def apply_theme(self, name: str):
        self.theme = name if name in THEMES else "dark"
        self.settings.setValue("ui/theme", self.theme)
        QApplication.instance().setStyleSheet(stylesheet(self.theme, checkmark_file(self.theme)))
        self.header.set_theme(self.theme)
        self.results.apply_theme(self.theme)
        self.live_page.apply_theme(self.theme)

    def _language_selected(self, code: str):
        if code == language():
            return
        if self.busy():
            QMessageBox.information(self, APP_NAME, tr("The language can be changed after the "
                                                       "measurement."))
            self.header.reset_language()
            return
        self._store_settings()
        self.settings.setValue("ui/language", code)
        self.language_change_requested.emit(code)

    def show_help(self):
        HelpDialog(self).exec()

    # ================================================================ pages / live
    def show_page(self, index: int):
        current = self.pages.currentIndex()
        self.header.show_page(index)
        if index == current:
            return
        if index == PAGE_LIVE and self.runner.busy:
            QMessageBox.information(self, APP_NAME, tr("Live mode is available after the "
                                                       "measurement."))
            self.header.show_page(current)
            return
        if index == PAGE_MEASUREMENT and self.live_page.running:
            if QMessageBox.question(self, APP_NAME, tr("Stop live mode?")) != QMessageBox.Yes:
                self.header.show_page(current)
                return
            self.live_page.shutdown()
        self.pages.setCurrentIndex(index)

    def _live_running_changed(self, running: bool):
        self._set_running(running)
        self.plan_card.set_stop_enabled(False)
        if not running:
            self._update_plan_info()  # live changes were taken over into the settings

    def _live_record_ready(self, record):
        self.runner.record = record
        self.results.show_record(record)

    # ================================================================ instruments
    def _run_task(self, fn, done, failed=None):
        task = Task(fn)
        self._tasks.add(task)

        def finish(ok, result):
            self._tasks.discard(task)
            (done if ok else (failed or (lambda e: self.log_message(e, "error"))))(result)

        task.signals.done.connect(lambda r: finish(True, r))
        task.signals.failed.connect(lambda e: finish(False, e))
        self.pool.start(task)

    def scan_devices(self):
        if self.busy():
            return
        self.store_configs()
        self.devices_card.set_scanning(True)
        self.plan_card.set_start_enabled(False)
        include_all = self.devices_card.all_ports.isChecked()
        self.settings.setValue("scan/all_ports", include_all)
        self.log_message(tr("Scanning serial ports for HP 34401A …"))
        self._run_task(lambda: discover(include_all, self.simulate), self._devices_found,
                       self._scan_failed)

    def _scan_failed(self, error):
        self.devices_card.set_scanning(False)
        self.log_message(tr("Scan failed: {error}", error=error), "error")
        self._update_start_enabled()

    def _devices_found(self, devices: list[DeviceInfo]):
        self.devices_card.set_scanning(False)
        devices.sort(key=lambda d: (d.label, d.port))
        self.devices = devices
        self.panels.clear()
        while self.settings_tabs.count():
            widget = self.settings_tabs.widget(0)
            self.settings_tabs.removeTab(0)
            widget.deleteLater()

        rows = []
        loop = self.plan_card.is_loop()
        for index, info in enumerate(devices):
            row = DeviceRow(info, DEVICE_COLORS[index % len(DEVICE_COLORS)])
            row.selected.connect(self._select_device)
            row.advanced.connect(self.open_advanced)
            row.toggled.connect(self._update_start_enabled)
            row.toggled.connect(self._update_plan_info)
            rows.append(row)
            panel = DeviceSettingsPanel(self._load_config(info))
            panel.set_loop_mode(loop)
            panel.changed.connect(self._update_plan_info)
            panel.changed.connect(self._update_start_enabled)
            panel.apply_mode_requested.connect(lambda i=info: self.apply_mode(i))
            self.panels[info.port] = panel
            self.settings_tabs.addTab(panel, info.label)
            self._log_found(info)
        self.devices_card.set_rows(rows)

        labels = [d.label for d in devices]
        if len(set(labels)) != len(labels):
            self.log_message(tr("Several instruments have the same ID – to measure "
                                "simultaneously, please assign unique IDs under ⚙."), "warn")
        self.settings_stack.setCurrentIndex(1 if devices else 0)
        if not devices:
            self.log_message(tr("No HP 34401A found."), "warn")
        else:
            self.log_message(tr("{n} instrument(s) ready.", n=len(devices)))
        self._select_device(devices[0] if devices else None)
        self._fit_sidebar()
        self._update_start_enabled()
        self._update_plan_info()

    def _log_found(self, info: DeviceInfo):
        text = f"{info.label} – {info.port}"
        if info.usb_serial:
            text += f" (USB {info.usb_serial})"
        self.log_message(tr("Found: {device}", device=text))
        if not (info.calibration_message or "").strip():
            self.log_message(tr("{port}: no ID stored. Please assign a unique ID under ⚙.",
                                port=info.port), "warn")
        if info.terminals.startswith("REAR"):
            self.log_message(tr("{device}: inputs switched to the REAR panel.",
                                device=info.label), "warn")

    def _select_device(self, info):
        for index, row in enumerate(self.rows):
            row.set_selected(row.info is info)
            if row.info is info:
                self.settings_tabs.setCurrentIndex(index)

    def _tab_changed(self, index):
        for i, row in enumerate(self.rows):
            row.set_selected(i == index)

    def _show_last_value(self, info: DeviceInfo, value: float):
        panel = self.panels.get(info.port)
        if panel is not None:
            panel.set_last_value(value)

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
        """Switch the instrument into a mode without data logging (e.g. continuity)."""
        if self.busy():
            return
        panel = self.panels[info.port]
        config = panel.config()
        problems = validate(config)
        if problems:
            QMessageBox.warning(self, APP_NAME, "\n".join(problems))
            return
        name = tr(config.func.label)
        self.log_message(tr("Switching {device} to \"{function}\" …", device=info.label,
                            function=name))
        panel.set_busy(True)

        def done(_):
            panel.set_busy(False)
            self.log_message(tr("{device} is in \"{function}\" mode – the front panel is active "
                                "again.", device=info.label, function=name))

        def failed(error):
            panel.set_busy(False)
            self.log_message(f"{info.label}: {error}", "error")
            QMessageBox.critical(self, APP_NAME, f"{info.label}: {error}")

        self._run_task(lambda: set_mode_only(info, config), done, failed)

    # ================================================================ stored settings
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

    def store_configs(self):
        for info in self.devices:
            panel = self.panels.get(info.port)
            if panel is not None:
                self.settings.setValue(self._config_key(info), json.dumps(panel.config().to_dict()))

    def _store_settings(self):
        self.store_configs()
        self.plan_card.store(self.settings)
        self.settings.setValue("export/csv_format", self.csv_format)

    # ================================================================ plan
    def _loop_mode_changed(self, loop: bool):
        for panel in self.panels.values():
            panel.set_loop_mode(loop)

    def _update_start_enabled(self):
        selected = self.selected_devices()
        self.plan_card.set_start_enabled(
            not self.runner.busy and bool(selected)
            and all(is_loggable(config) for _, config in selected))

    def _update_plan_info(self):
        self.plan_card.update_info([config for _, config in self.selected_devices()])

    def _set_running(self, running: bool):
        self.plan_card.set_running(running)
        self.devices_card.set_running(running)
        self.profile_card.set_running(running)
        for panel in self.panels.values():
            panel.set_busy(running)
        self.export_card.format_combo.setEnabled(not running)
        self.header.language_combo.setEnabled(not running)
        record = self.runner.record
        self.export_card.set_exports_enabled(not running and record is not None and any(
            rec.readings for rec in record.devices))
        if not running:
            self._update_start_enabled()

    # ================================================================ measurement
    def start_measurement(self):
        selected = self.selected_devices()
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
        blocked = not_loggable_text([config for _, config in selected])
        if blocked:
            QMessageBox.information(self, APP_NAME, blocked.lstrip("⚠ "))
            return
        plan = self.plan_card.plan()
        if plan.stability is not None and plan.duration == 0:
            QMessageBox.warning(self, APP_NAME, tr("\"Measure until stable\" needs a maximum "
                                                   "duration (not \"1 reading\")."))
            return
        loop = self.plan_card.is_loop()
        if loop:
            objects = self.plan_card.objects()
            if not objects:
                QMessageBox.warning(self, APP_NAME, tr("The object list of the series is empty."))
                return
            steps = build_loop_steps(selected, objects)
        else:
            steps = [selected]
        self._store_settings()

        record = MeasurementRecord([], plan.interval, plan.duration,
                                   note=self.plan_card.note.text().strip(), loop=loop,
                                   profile=self.current_profile, stability=plan.stability)
        writer = self._open_autosave(record, steps[0], selected)
        loop_state = (LoopState(steps, self.plan_card.advance.currentData(),
                                self.plan_card.pause.value()) if loop else None)
        self.runner.start(steps, plan, record, writer, loop_state)

    def _open_autosave(self, record: MeasurementRecord, first_step, selected):
        """Create the continuously written autosave CSV; None if that is not possible."""
        record.devices = [DeviceRecord(i, c) for i, c in first_step]  # for the CSV columns
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        names = "_".join(safe_name(i.label) or "dev" for i, _ in selected)
        try:
            return LiveCsvWriter(autosave_dir() / f"{stamp}_{names}.csv", record, self.csv_format)
        except OSError as error:
            self.log_message(tr("Autosave not possible: {error}", error=error), "warn")
            return None
        finally:
            record.devices = []

    # ================================================================ test profiles
    def save_profile(self):
        if not self.rows:
            QMessageBox.information(self, APP_NAME, tr("Scan for instruments first."))
            return
        name = self.profile_card.ask_name()
        if name is None:
            return
        plan = self.plan_card.profile_data()
        plan["csv_format"] = self.csv_format
        devices = [{"id": row.info.label, "use": row.use.isChecked(),
                    "config": self.panels[row.info.port].config().to_dict()} for row in self.rows]
        try:
            save_profile(name, plan, devices)
        except OSError as error:
            QMessageBox.critical(self, APP_NAME, str(error))
            return
        self.profile_card.saved(name)

    def apply_profile(self, profile: dict):
        if self.busy():
            return
        plan = profile["plan"]
        self.plan_card.apply_profile(plan)
        if plan.get("csv_format"):
            self.export_card.select_format(plan["csv_format"])

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
        self.profile_card.set_current(str(profile.get("name", "")))
        self._loop_mode_changed(self.plan_card.is_loop())
        self._update_plan_info()
        self._update_start_enabled()
        self.log_message(tr("Test profile \"{name}\" loaded.", name=self.current_profile))

    # ================================================================ export
    def _save_path(self, title: str, file_name: str, file_filter: str, suffix: str) -> str | None:
        folder = self.settings.value("export/folder", str(Path.home()))
        path, _ = QFileDialog.getSaveFileName(self, title, str(Path(folder) / file_name),
                                              file_filter)
        if not path:
            return None
        if not path.lower().endswith(suffix):
            path += suffix
        return path

    def _exported(self, path: str):
        self.settings.setValue("export/folder", str(Path(path).parent))
        self.log_message(tr("Exported: {path}", path=path))

    def export_chart(self, widget=None):
        widget = widget or self.results.plot_widget
        if widget is self.results.plot_widget and not self.results.has_chart:
            return
        record = self.runner.record
        started = record.started_at if record is not None else None
        stamp = (started or datetime.now()).strftime("%Y%m%d_%H%M%S")
        path = self._save_path(tr("Save chart"), f"HPMulti_{stamp}_chart.png",
                               tr("PNG image (*.png)"), ".png")
        if path is None:
            return
        if not render_png(widget, path, self.theme):
            QMessageBox.critical(self, APP_NAME, tr("Export failed: {error}", error=path))
            return
        self._exported(path)

    def export(self, kind: str):
        record = self.runner.record
        if record is None:
            return
        stamp = (record.started_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
        names = "-".join(dict.fromkeys(safe_name(rec.info.label) or "dev"
                                       for rec in record.devices))
        file_filter = tr("CSV file (*.csv)") if kind == "csv" else tr("Text file (*.txt)")
        path = self._save_path(tr("Export readings"), f"HPMulti_{stamp}_{names}.{kind}",
                               file_filter, f".{kind}")
        if path is None:
            return
        try:
            if kind == "csv":
                write_csv(record, Path(path), self.csv_format)
            else:
                write_txt(record, Path(path))
        except OSError as error:
            QMessageBox.critical(self, APP_NAME, tr("Export failed: {error}", error=error))
            return
        self.settings.setValue("export/csv_format", self.csv_format)
        self._exported(path)

    # ================================================================ close
    def shutdown(self) -> bool:
        """Stop running work and save settings. False if the user cancelled."""
        if self.live_page.running:
            if self.live_page.recording and QMessageBox.question(
                    self, APP_NAME, tr("A live recording is running. Stop it and quit?")) \
                    != QMessageBox.Yes:
                return False
            self.live_page.shutdown()
        if self.runner.busy:
            if QMessageBox.question(self, APP_NAME, tr("A measurement is running. Stop and "
                                                       "quit?")) != QMessageBox.Yes:
                return False
            self.runner.shutdown()
        self._store_settings()
        self.settings.setValue("ui/geometry", self.saveGeometry())
        return True

    def closeEvent(self, event):  # noqa: N802 - Qt naming
        if not self.shutdown():
            event.ignore()
            return
        super().closeEvent(event)
