"""Sidebar card "Measurement": mode, duration, interval, stability, series objects, start/stop."""

from __future__ import annotations

import json

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDoubleSpinBox, QHBoxLayout,
                               QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from ..acquisition import Plan, Stability
from ..functions import DeviceConfig, estimated_reading_time
from ..i18n import localize_number, tr
from ..series import (ADVANCE_AUTO, ADVANCE_CONFIRM, LOOP_TEMPLATES, MODE_LOOP, MODE_SINGLE,
                      step_count)
from .time_input import DURATION_PRESETS, INTERVAL_PRESETS, TimeInput
from .widgets import Card, DataCombo, FormRow, muted

PROGRESS_STEPS = 1000


class PlanCard(Card):
    changed = Signal()               # anything that affects the plan summary
    mode_changed = Signal(bool)      # True = measurement series (loop)
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, settings: QSettings):
        super().__init__(tr("Measurement"))
        self._ready = False
        self.mode = DataCombo()
        self.mode.set_items([(MODE_SINGLE, tr("Continuous measurement")),
                             (MODE_LOOP, tr("Measurement series (loop): objects one after another"))],
                            settings.value("plan/mode", MODE_SINGLE))
        self.body.addWidget(FormRow(tr("Mode"), self.mode))
        self.body.addWidget(self._build_loop_editor(settings))
        self.duration = TimeInput(DURATION_PRESETS, 60)
        self.interval = TimeInput(INTERVAL_PRESETS, 1)
        duration = settings.value("plan/duration", 60)
        self.duration.set_seconds(None if duration in (None, "", "None") else float(duration))
        self.interval.set_seconds(float(settings.value("plan/interval", 1)))
        self.duration_row = FormRow(tr("How long should it measure?"), self.duration)
        self.body.addWidget(self.duration_row)
        self.body.addWidget(FormRow(tr("Interval"), self.interval))
        self.body.addWidget(self._build_stability_editor(settings))
        self.info = muted("")
        self.body.addWidget(self.info)
        self.note = QLineEdit()
        self.note.setPlaceholderText(tr("Note for the report (optional)"))
        self.body.addWidget(self.note)
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
        self.body.addLayout(buttons)
        self.progress = QProgressBar()
        self.progress.setRange(0, PROGRESS_STEPS)
        self.progress.setValue(0)
        self.progress_label = muted("")
        self.body.addWidget(self.progress)
        self.body.addWidget(self.progress_label)

        self.start_button.clicked.connect(self.start_requested)
        self.stop_button.clicked.connect(self.stop_requested)
        self.duration.changed.connect(self._emit_changed)
        self.interval.changed.connect(self._emit_changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.advance.currentIndexChanged.connect(self._mode_changed)
        self.stability_on.toggled.connect(self._mode_changed)
        self._ready = True
        self._mode_changed()

    # ------------------------------------------------------------------ building
    def _build_stability_editor(self, settings: QSettings) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.stability_on = QCheckBox(tr("Measure until stable"))
        self.stability_on.setChecked(settings.value("stability/on", False, type=bool))
        self.stability_window = QSpinBox()
        self.stability_window.setRange(2, 1000)
        self.stability_window.setValue(int(settings.value("stability/window", 10)))
        self.stability_limit = QDoubleSpinBox()
        self.stability_limit.setRange(0, 1e9)
        self.stability_limit.setDecimals(6)
        self.stability_limit.setValue(float(settings.value("stability/limit", 0.01)))
        self.stability_mode = DataCombo()
        self.stability_mode.set_items([(True, tr("% of the reading")),
                                       (False, tr("absolute (unit of the reading)"))],
                                      settings.value("stability/relative", True, type=bool))
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
        for widget in (self.stability_window, self.stability_limit):
            widget.valueChanged.connect(self._emit_changed)
        self.stability_editor = box
        return box

    def _build_loop_editor(self, settings: QSettings) -> QWidget:
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
        self.object_list.model().rowsMoved.connect(self._emit_changed)
        self.object_list.itemChanged.connect(self._emit_changed)
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
        clear.clicked.connect(lambda: self.set_objects([]))
        row.addWidget(self.new_object, 1)
        row.addWidget(add)
        row.addWidget(remove)
        row.addWidget(clear)
        layout.addLayout(row)
        self.advance = DataCombo()
        self.advance.set_items([(ADVANCE_CONFIRM, tr("After confirmation (button / Enter)")),
                                (ADVANCE_AUTO, tr("Automatically after a pause"))],
                               settings.value("loop/advance", ADVANCE_CONFIRM))
        self.pause = QDoubleSpinBox()
        self.pause.setRange(0, 3600)
        self.pause.setDecimals(1)
        self.pause.setSuffix(" s")
        self.pause.setValue(float(settings.value("loop/pause", 5)))
        self.pause_row = FormRow(tr("Pause for reconnecting"), self.pause)
        layout.addWidget(FormRow(tr("Next object"), self.advance))
        layout.addWidget(self.pause_row)
        try:
            objects = json.loads(settings.value("loop/objects", "[]"))
        except (TypeError, ValueError):
            objects = []
        for name in objects:
            self._append_object(name)
        self.loop_editor = box
        return box

    # ------------------------------------------------------------------ objects
    def objects(self) -> list[str]:
        return [self.object_list.item(i).text().strip() for i in range(self.object_list.count())
                if self.object_list.item(i).text().strip()]

    def set_objects(self, names):
        self.object_list.clear()
        for name in names:
            self._append_object(str(name))
        self._emit_changed()

    def _append_object(self, name: str):
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.object_list.addItem(item)

    def _add_object(self):
        for name in [n.strip() for n in self.new_object.text().split(",")]:
            if name:
                self._append_object(name)
        self.new_object.clear()
        self._emit_changed()

    def _remove_object(self):
        for item in self.object_list.selectedItems():
            self.object_list.takeItem(self.object_list.row(item))
        self._emit_changed()

    def _apply_template(self):
        index = self.template.currentData()
        if index is None:
            return
        # A template replaces the current list.
        self.set_objects(name.strip() for name in tr(LOOP_TEMPLATES[index][1]).split(","))
        self.template.setCurrentIndex(0)

    # ------------------------------------------------------------------ state
    def is_loop(self) -> bool:
        return self.mode.currentData() == MODE_LOOP

    def stability(self) -> Stability | None:
        if not self.stability_on.isChecked():
            return None
        return Stability(self.stability_window.value(), self.stability_limit.value(),
                         bool(self.stability_mode.currentData()))

    def plan(self) -> Plan:
        return Plan(interval=float(self.interval.seconds() or 0), duration=self.duration.seconds(),
                    stability=self.stability())

    def _emit_changed(self, *args):
        if self._ready:
            self.changed.emit()

    def _mode_changed(self):
        if not self._ready:
            return
        loop = self.is_loop()
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
        self.mode_changed.emit(loop)
        self.changed.emit()

    def update_info(self, configs: list[DeviceConfig]):
        """Summarise the plan for the selected instruments (their configurations)."""
        plan = self.plan()
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
        if self.is_loop():
            selected = len(configs) or 1
            objects = len(self.objects())
            parts.insert(0, tr("{objects} objects · {devices} instrument(s) → {steps} steps",
                               objects=objects, devices=selected,
                               steps=step_count(objects, selected)))
            if plan.duration is None:
                parts.append(tr("⚠ Unlimited: every step runs until stopped"))
        slowest = max((estimated_reading_time(config) for config in configs), default=0)
        if plan.interval > 0 and slowest > plan.interval:
            parts.append(tr("⚠ one reading takes ≈ {s} s – longer than the interval",
                            s=localize_number(f"{slowest:.1f}")))
        self.info.setText(" · ".join(parts))

    def set_running(self, running: bool):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        for widget in (self.duration, self.interval, self.note, self.mode, self.loop_editor,
                       self.stability_editor):
            widget.setEnabled(not running)

    def set_start_enabled(self, enabled: bool):
        self.start_button.setEnabled(enabled)

    def set_stop_enabled(self, enabled: bool):
        self.stop_button.setEnabled(enabled)

    # ------------------------------------------------------------------ progress
    def reset_progress(self, full: bool = False):
        self.progress.setRange(0, PROGRESS_STEPS)
        self.progress.setValue(PROGRESS_STEPS if full else 0)

    def set_progress(self, fraction: float | None):
        """``None`` shows a busy indicator (unlimited duration)."""
        if fraction is None:
            self.progress.setRange(0, 0)
        else:
            self.progress.setValue(int(min(1.0, fraction) * PROGRESS_STEPS))

    def set_progress_text(self, text: str):
        self.progress_label.setText(text)

    # ------------------------------------------------------------------ persistence
    def store(self, settings: QSettings):
        plan = self.plan()
        settings.setValue("plan/duration", "None" if plan.duration is None else plan.duration)
        settings.setValue("plan/interval", plan.interval)
        settings.setValue("plan/mode", self.mode.currentData())
        settings.setValue("loop/objects", json.dumps(self.objects()))
        settings.setValue("loop/advance", self.advance.currentData())
        settings.setValue("loop/pause", self.pause.value())
        settings.setValue("stability/on", self.stability_on.isChecked())
        settings.setValue("stability/window", self.stability_window.value())
        settings.setValue("stability/limit", self.stability_limit.value())
        settings.setValue("stability/relative", bool(self.stability_mode.currentData()))

    def profile_data(self) -> dict:
        """The plan as stored in a test profile."""
        return {
            "mode": self.mode.currentData(),
            "duration": self.duration.seconds(),
            "interval": float(self.interval.seconds() or 0),
            "objects": self.objects(),
            "advance": self.advance.currentData(),
            "pause": self.pause.value(),
            "stability": {"on": self.stability_on.isChecked(),
                          "window": self.stability_window.value(),
                          "limit": self.stability_limit.value(),
                          "relative": bool(self.stability_mode.currentData())},
        }

    def apply_profile(self, plan: dict):
        if plan.get("mode"):
            self.mode.select_data(plan["mode"])
        if "duration" in plan:
            self.duration.set_seconds(plan["duration"])
        if "interval" in plan:
            self.interval.set_seconds(plan["interval"])
        if isinstance(plan.get("objects"), list):
            self.set_objects(plan["objects"])
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
        self._mode_changed()
