"""Input for a duration or interval: preset list plus a custom value with unit."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QVBoxLayout, QWidget

from ..i18n import N_, tr
from .widgets import DataCombo

CUSTOM = -1
DURATION_PRESETS = [(None, N_("Unlimited (until stopped)")), (0, N_("1 reading (single measurement)")),
                    (10, N_("10 seconds")), (30, N_("30 seconds")), (60, N_("1 minute")),
                    (120, N_("2 minutes")), (300, N_("5 minutes")), (600, N_("10 minutes")),
                    (1800, N_("30 minutes")), (3600, N_("1 hour")), (7200, N_("2 hours")),
                    (28800, N_("8 hours")), (86400, N_("24 hours")),
                    (CUSTOM, N_("Custom …"))]
INTERVAL_PRESETS = [(0, N_("As fast as possible")), (0.1, N_("0.1 s")), (0.2, N_("0.2 s")),
                    (0.5, N_("0.5 s")), (1, "1 s"), (2, "2 s"), (5, "5 s"), (10, "10 s"),
                    (30, "30 s"), (60, "1 min"), (300, "5 min"), (600, "10 min"),
                    (CUSTOM, N_("Custom …"))]
TIME_UNITS = [(1, "s"), (60, "min"), (3600, "h")]


def hms(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


class TimeInput(QWidget):
    """Preset combo plus custom value/unit fields."""

    changed = Signal()

    def __init__(self, presets, default):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.combo = DataCombo()
        self.combo.set_items([(value, tr(text)) for value, text in presets], default)
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
        self.custom.setVisible(self.combo.currentData() == CUSTOM)
        self.changed.emit()

    def seconds(self):
        data = self.combo.currentData()
        if data == CUSTOM:
            return self.value.value() * self.unit.currentData()
        return data

    def set_seconds(self, seconds):
        if not self.combo.select_data(seconds):
            self.combo.select_data(CUSTOM)
            factor = 1
            for factor, _ in reversed(TIME_UNITS):
                if seconds >= factor and abs(seconds / factor - round(seconds / factor, 3)) < 1e-9:
                    break
            self.unit.select_data(factor)
            self.value.setValue(seconds / factor)
