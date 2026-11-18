"""Advanced settings per instrument: info, ID change, diagnostics."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRegularExpression, QThreadPool, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QRegularExpressionValidator
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..device_id import (DEFAULT_SECURITY_CODE, DISPLAY_LENGTH, MAX_LENGTH, validate_id,
                         write_device_id)
from ..i18n import tr
from ..instrument import DeviceInfo, open_instrument
from ..paths import backup_dir
from .widgets import Card, FormRow, Task, hint, muted


def _with_meter(info: DeviceInfo, action):
    meter = open_instrument(info)
    try:
        meter.connect()
        return action(meter)
    finally:
        meter.close()


def _read_details(meter) -> dict:
    return {
        "idn": meter.identify(),
        "message": meter.calibration_message(),
        "count": meter.calibration_count(),
        "secured": meter.calibration_secured(),
        "terminals": meter.terminals(),
        "version": meter.query("SYST:VERS?"),
        "errors": meter.read_errors(),
    }


class AdvancedDialog(QDialog):
    id_changed = Signal(object)  # DeviceInfo

    def __init__(self, info: DeviceInfo, other_labels: list[str], parent=None):
        super().__init__(parent)
        self.info = info
        self.other_labels = other_labels
        self.pool = QThreadPool.globalInstance()
        self._tasks = set()
        self.setWindowTitle(tr("Advanced settings – {device}", device=info.label))
        self.resize(660, 840)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        scroll.setWidget(inner)
        root = QVBoxLayout(inner)
        root.setSpacing(12)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.addWidget(scroll)

        # info ------------------------------------------------------------
        card = Card(tr("Instrument information"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        self.info_labels = {}
        rows = [(tr("ID (CAL:STR)"), "message"), (tr("Port"), "port"),
                (tr("USB serial number"), "usb"), (tr("Identification"), "idn"),
                (tr("SCPI version"), "version"), (tr("Calibration count"), "count"),
                (tr("Calibration security"), "secured"), (tr("Input terminals"), "terminals"),
                (tr("Error queue"), "errors")]
        for row, (title, key) in enumerate(rows):
            grid.addWidget(muted(title, wrap=False), row, 0, Qt.AlignTop)
            value = QLabel("–")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(value, row, 1)
            self.info_labels[key] = value
        card.body.addLayout(grid)
        self.refresh_button = QPushButton(tr("Read from instrument"))
        self.refresh_button.clicked.connect(self.refresh)
        card.body.addWidget(self.refresh_button, alignment=Qt.AlignLeft)
        root.addWidget(card)

        # ID ---------------------------------------------------------------
        card = Card(tr("Change instrument ID"),
                    tr("The ID is stored in the instrument as its calibration message "
                       "(CAL:STRing) and identifies the multimeter uniquely, independent of the "
                       "COM port."))
        self.new_id = QLineEdit()
        self.new_id.setMaxLength(MAX_LENGTH)
        self.new_id.setValidator(QRegularExpressionValidator(QRegularExpression(r"[ -~]*"), self))
        self.new_id.setPlaceholderText(tr("e.g. T050"))
        self.id_counter = muted("")
        self.code = QLineEdit()
        self.code.setEchoMode(QLineEdit.Password)
        self.code.setPlaceholderText(tr("empty = factory default {code}",
                                        code=DEFAULT_SECURITY_CODE))
        self.confirm = QCheckBox(tr("I have checked that this is the right instrument"))
        self.write_button = QPushButton(tr("Write ID"))
        self.write_button.setObjectName("Primary")
        self.write_button.setEnabled(False)
        card.body.addWidget(FormRow(tr("New ID (max. 40 characters, the display shows 12)"),
                                    self.new_id))
        card.body.addWidget(self.id_counter)
        card.body.addWidget(FormRow(tr("Calibration security code"), self.code))
        card.body.addWidget(hint(tr(
            "Procedure: JSON backup → disable calibration security with the code → write the "
            "ID and read it back → enable calibration security again. The calibration count "
            "and the calibration constants are not changed. The code is not stored.")))
        card.body.addWidget(self.confirm)
        row = QHBoxLayout()
        row.addWidget(self.write_button)
        open_backups = QPushButton(tr("Open backup folder"))
        open_backups.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(backup_dir()))))
        row.addWidget(open_backups)
        row.addStretch(1)
        card.body.addLayout(row)
        root.addWidget(card)
        self.new_id.textChanged.connect(self._id_input_changed)
        self.confirm.toggled.connect(self._id_input_changed)
        self.write_button.clicked.connect(self.write_id)

        # diagnostics -----------------------------------------------------------
        card = Card(tr("Diagnostics"))
        buttons = QGridLayout()
        self.selftest_button = QPushButton(tr("Self-test (*TST?)"))
        self.errors_button = QPushButton(tr("Read error queue"))
        self.reset_button = QPushButton(tr("Reset instrument (*RST)"))
        self.beep_button = QPushButton(tr("Test beeper"))
        buttons.addWidget(self.selftest_button, 0, 0)
        buttons.addWidget(self.errors_button, 0, 1)
        buttons.addWidget(self.reset_button, 1, 0)
        buttons.addWidget(self.beep_button, 1, 1)
        card.body.addLayout(buttons)
        root.addWidget(card)
        self.selftest_button.clicked.connect(self.self_test)
        self.errors_button.clicked.connect(self.read_errors)
        self.reset_button.clicked.connect(self.reset_device)
        self.beep_button.clicked.connect(
            lambda: self._run(tr("Beeper"), lambda m: m.write("SYST:BEEP") or tr("beeped")))

        # log -------------------------------------------------------------------
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)
        root.addWidget(self.log)

        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        outer.addWidget(close)

        self._show_static()
        self._id_input_changed()
        self.refresh()

    # ------------------------------------------------------------------------
    def _log(self, text: str):
        self.log.appendPlainText(f"{datetime.now():%H:%M:%S}  {text}")

    def _show_static(self):
        info = self.info
        self.info_labels["message"].setText(repr(info.calibration_message))
        self.info_labels["port"].setText(f"{info.port}  ({info.port_description})")
        self.info_labels["usb"].setText(info.usb_serial or "–")
        self.info_labels["idn"].setText(info.identification)

    def _set_busy(self, busy: bool):
        for button in (self.refresh_button, self.selftest_button, self.errors_button,
                       self.reset_button, self.beep_button):
            button.setEnabled(not busy)
        self.write_button.setEnabled(not busy and self._id_ok())

    def _start(self, fn, on_done, label: str, on_error=None):
        task = Task(fn)
        self._tasks.add(task)
        self._set_busy(True)

        def finished(ok, result):
            self._tasks.discard(task)
            self._set_busy(False)
            if ok:
                on_done(result)
            else:
                self._log(tr("{action}: ERROR – {error}", action=label, error=result))
                if on_error:
                    on_error(result)

        task.signals.done.connect(lambda r: finished(True, r))
        task.signals.failed.connect(lambda e: finished(False, e))
        self.pool.start(task)

    def _run(self, label, action):
        self._start(lambda: _with_meter(self.info, action),
                    lambda result: self._log(f"{label}: {result}"), label)

    # ------------------------------------------------------------------------
    def refresh(self):
        self._log(tr("Reading instrument information …"))
        self._start(lambda: _with_meter(self.info, _read_details), self._show_details,
                    tr("Read"))

    def _show_details(self, d: dict):
        self.info_labels["message"].setText(repr(d["message"]))
        self.info_labels["idn"].setText(d["idn"])
        self.info_labels["version"].setText(d["version"])
        self.info_labels["count"].setText(str(d["count"]))
        self.info_labels["secured"].setText(tr("secured") if d["secured"] else tr("NOT secured"))
        terminals = {"FRON": tr("Front"), "REAR": tr("Rear")}.get(d["terminals"], d["terminals"])
        self.info_labels["terminals"].setText(
            terminals + "  " + tr("(switch on the instrument, cannot be set remotely)"))
        self.info_labels["errors"].setText("; ".join(d["errors"]) or tr("none"))
        self._log(tr("Instrument information updated."))

    def _id_ok(self) -> bool:
        text = self.new_id.text()
        return (not validate_id(text) and self.confirm.isChecked()
                and text != self.info.calibration_message)

    def _id_input_changed(self):
        text = self.new_id.text()
        notes = [tr("{n}/{max} characters", n=len(text), max=MAX_LENGTH)]
        if len(text) > DISPLAY_LENGTH:
            notes.append(tr("the display shows only the first {n}", n=DISPLAY_LENGTH))
        if text and text in self.other_labels:
            notes.append(tr("⚠ another instrument already has this ID"))
        if text and text != text.strip():
            notes.append(tr("note: leading/trailing spaces are stored too"))
        self.id_counter.setText(" · ".join(notes))
        self.write_button.setEnabled(self._id_ok())

    def write_id(self):
        new_id = self.new_id.text()
        code = self.code.text().strip() or DEFAULT_SECURITY_CODE
        if new_id in self.other_labels:
            QMessageBox.warning(self, tr("ID not unique"),
                                tr("Another connected instrument already has this ID."))
            return
        answer = QMessageBox.question(
            self, tr("Write ID"),
            tr("Change the ID of the instrument on {port}?\n\nOld: {old!r}\nNew: {new!r}\n\n"
               "A backup is created automatically first.", port=self.info.port,
               old=self.info.calibration_message, new=new_id))
        if answer != QMessageBox.Yes:
            return
        messages = []

        def done(_backup_path):
            for message in messages:
                self._log(message)
            self._log(tr("ID changed successfully: {id!r}", id=new_id))
            self.code.clear()
            self.confirm.setChecked(False)
            self.setWindowTitle(tr("Advanced settings – {device}", device=self.info.label))
            self.id_changed.emit(self.info)
            self.refresh()

        def failed(error):
            for message in messages:
                self._log(message)
            QMessageBox.critical(self, tr("ID not written"), str(error))

        self._log(tr("Writing ID {id!r} …", id=new_id))
        self._start(lambda: write_device_id(self.info, new_id, code, log=messages.append),
                    done, tr("Write ID"), failed)

    def self_test(self):
        self._log(tr("Self-test running (approx. 10 s) …"))

        def action(meter):
            result = meter.query("*TST?", timeout=60).strip().lstrip("+")
            return tr("passed") if result == "0" else tr("FAILED (code {code})", code=result)

        self._run(tr("Self-test"), action)

    def read_errors(self):
        self._run(tr("Error queue"), lambda m: "; ".join(m.read_errors()) or tr("no errors"))

    def reset_device(self):
        if QMessageBox.question(self, tr("Reset"),
                                tr("Reset the instrument to its power-on state (*RST)?")) \
                != QMessageBox.Yes:
            return
        self._run(tr("Reset"), lambda m: m.write("*RST") or tr("instrument reset"))
