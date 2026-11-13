"""Entry for one detected instrument in the sidebar list."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout

from ..i18n import tr
from ..instrument import DeviceInfo
from .widgets import StatusDot, muted


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

    def mousePressEvent(self, event):  # noqa: N802 - Qt naming
        self.selected.emit(self.info)
        super().mousePressEvent(event)
