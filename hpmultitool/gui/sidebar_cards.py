"""Sidebar cards "Instruments", "Test profile" and "Export"."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QInputDialog, QMessageBox, QPushButton,
                               QToolButton, QVBoxLayout)

from .. import APP_NAME
from ..export import CSV_FORMATS
from ..i18n import tr
from ..paths import autosave_dir
from ..profiles import delete_profile, list_profiles, load_profile, profile_dir
from .device_list import DeviceRow
from .widgets import Card, DataCombo, FormRow, hint, muted


def open_folder(path: Path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class DevicesCard(Card):
    scan_requested = Signal()

    def __init__(self, settings: QSettings):
        super().__init__(tr("Instruments"))
        self.rows: list[DeviceRow] = []
        self.list = QVBoxLayout()
        self.list.setSpacing(6)
        self.body.addLayout(self.list)
        self.empty = hint(tr("No instruments found yet. Switch the multimeter on, set its "
                             "interface to RS-232 (9600 baud, even parity) and scan."))
        self.body.addWidget(self.empty)
        self.scan_button = QPushButton()
        self.scan_button.clicked.connect(self.scan_requested)
        self.all_ports = QCheckBox(tr("Also probe ports without a USB ID"))
        self.all_ports.setChecked(settings.value("scan/all_ports", False, type=bool))
        self.body.addWidget(self.scan_button)
        self.body.addWidget(self.all_ports)
        self.set_scanning(False)

    def set_scanning(self, scanning: bool):
        self.scan_button.setEnabled(not scanning)
        self.scan_button.setText(tr("Scanning …") if scanning else tr("⟳  Scan for instruments"))

    def set_rows(self, rows: list[DeviceRow]):
        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = list(rows)
        for row in self.rows:
            self.list.addWidget(row)
        self.empty.setVisible(not self.rows)

    def checked_rows(self) -> list[DeviceRow]:
        return [row for row in self.rows if row.use.isChecked()]

    def set_running(self, running: bool):
        self.scan_button.setEnabled(not running)
        for row in self.rows:
            row.use.setEnabled(not running)


class ProfileCard(Card):
    """Choose, load, save and delete test profiles. The window applies and collects the data."""

    save_requested = Signal()
    load_requested = Signal(dict)
    message = Signal(str)

    def __init__(self):
        super().__init__(tr("Test profile"))
        self.current = ""
        self._idle = True
        self.combo = DataCombo()
        self.state = muted("")
        row = QHBoxLayout()
        self.load_button = QPushButton(tr("Load"))
        self.save_button = QPushButton(tr("Save …"))
        self.delete_button = QToolButton()
        self.delete_button.setText("🗑")
        self.delete_button.setToolTip(tr("Delete the selected profile"))
        folder = QToolButton()
        folder.setText("📁")
        folder.setToolTip(tr("Open the profile folder (profiles can be copied to "
                             "other computers)"))
        for widget in (self.load_button, self.save_button, self.delete_button, folder):
            row.addWidget(widget)
        self.body.addWidget(self.combo)
        self.body.addLayout(row)
        self.body.addWidget(self.state)
        self.load_button.clicked.connect(self._load_selected)
        self.save_button.clicked.connect(self.save_requested)
        self.delete_button.clicked.connect(self._delete_selected)
        folder.clicked.connect(lambda: open_folder(profile_dir()))
        self.combo.currentIndexChanged.connect(self._update_buttons)
        self.refresh()
        self._show_state()

    def refresh(self, select: str = ""):
        self.combo.set_items([(None, tr("Select a profile …"))] + [
            (str(path), name) for name, path in list_profiles()])
        if select:
            for index in range(self.combo.count()):
                if self.combo.itemText(index) == select:
                    self.combo.setCurrentIndex(index)
        self._update_buttons()

    def set_running(self, running: bool):
        self._idle = not running
        for widget in (self.combo, self.load_button, self.save_button, self.delete_button):
            widget.setEnabled(not running)
        self._update_buttons()

    def _update_buttons(self):
        selected = self.combo.currentData() is not None
        self.load_button.setEnabled(selected and self._idle)
        self.delete_button.setEnabled(selected and self._idle)

    def ask_name(self) -> str | None:
        """Ask for the name to save under (confirming an overwrite); None = cancelled."""
        name, ok = QInputDialog.getText(self, tr("Save test profile"), tr("Profile name:"),
                                        text=self.current)
        name = name.strip()
        if not ok or not name:
            return None
        if any(existing.lower() == name.lower() for existing, _ in list_profiles()):
            if QMessageBox.question(self, APP_NAME, tr("Overwrite the profile \"{name}\"?",
                                                       name=name)) != QMessageBox.Yes:
                return None
        return name

    def saved(self, name: str):
        self.set_current(name)
        self.refresh(select=name)
        self.message.emit(tr("Test profile \"{name}\" saved.", name=name))

    def set_current(self, name: str):
        self.current = name
        self._show_state()

    def _load_selected(self):
        path = self.combo.currentData()
        if path is None or not self._idle:
            return
        try:
            profile = load_profile(Path(path))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, APP_NAME, tr("Profile could not be loaded: {error}",
                                                    error=error))
            return
        self.load_requested.emit(profile)

    def _delete_selected(self):
        path = self.combo.currentData()
        if path is None:
            return
        name = self.combo.currentText()
        if QMessageBox.question(self, APP_NAME, tr("Delete the profile \"{name}\"?",
                                                   name=name)) != QMessageBox.Yes:
            return
        delete_profile(Path(path))
        if self.current == name:
            self.current = ""
        self.refresh()
        self._show_state()
        self.message.emit(tr("Test profile \"{name}\" deleted.", name=name))

    def _show_state(self):
        if self.current:
            self.state.setText(tr("Active profile: <b>{name}</b>", name=self.current))
        else:
            self.state.setText(tr("Saves the measurement plan and the settings of every "
                                  "instrument under a name."))


class ExportCard(Card):
    export_requested = Signal(str)   # "csv" or "txt"
    chart_requested = Signal()

    def __init__(self, settings: QSettings):
        super().__init__(tr("Export"))
        self.format_combo = DataCombo()
        self.format_combo.set_items([(k, tr(v["label"])) for k, v in CSV_FORMATS.items()],
                                    settings.value("export/csv_format", "de"))
        self.body.addWidget(FormRow(tr("CSV format"), self.format_combo))
        row = QHBoxLayout()
        self.csv_button = QPushButton(tr("As CSV …"))
        self.txt_button = QPushButton(tr("As TXT …"))
        self.csv_button.clicked.connect(lambda: self.export_requested.emit("csv"))
        self.txt_button.clicked.connect(lambda: self.export_requested.emit("txt"))
        row.addWidget(self.csv_button)
        row.addWidget(self.txt_button)
        self.body.addLayout(row)
        self.png_button = QPushButton(tr("Chart as PNG …"))
        self.png_button.clicked.connect(self.chart_requested)
        self.body.addWidget(self.png_button)
        autosave = QPushButton(tr("Open autosave folder"))
        autosave.setToolTip(str(autosave_dir()))
        autosave.clicked.connect(lambda: open_folder(autosave_dir()))
        self.body.addWidget(autosave)
        self.body.addWidget(muted(tr("Every measurement is also saved continuously as CSV in the "
                                     "autosave folder.")))
        self.set_exports_enabled(False)

    @property
    def csv_format(self) -> str:
        return self.format_combo.currentData()

    def select_format(self, code: str):
        self.format_combo.select_data(code)

    def set_exports_enabled(self, enabled: bool):
        for button in (self.csv_button, self.txt_button, self.png_button):
            button.setEnabled(enabled)
