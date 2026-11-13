"""Banner that guides through a measurement series: what to connect, measure, repeat, skip."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..i18n import tr


class LoopBanner(QFrame):
    measure_requested = Signal()
    repeat_requested = Signal()
    skip_requested = Signal()
    end_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("LoopBanner")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self.title = QLabel()
        self.title.setObjectName("BannerTitle")
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.RichText)
        layout.addWidget(self.title)
        layout.addWidget(self.text)
        buttons = QHBoxLayout()
        self.measure_button = QPushButton(tr("▶  Measure"))
        self.measure_button.setObjectName("Primary")
        self.measure_button.setMinimumHeight(36)
        self.measure_button.setShortcut(QKeySequence(Qt.Key_Return))
        self.repeat_button = QPushButton(tr("↺  Repeat last step"))
        self.skip_button = QPushButton(tr("Skip"))
        self.end_button = QPushButton(tr("End series"))
        self.end_button.setObjectName("Danger")
        for button in (self.measure_button, self.repeat_button, self.skip_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.end_button)
        layout.addLayout(buttons)
        self.measure_button.clicked.connect(self.measure_requested)
        self.repeat_button.clicked.connect(self.repeat_requested)
        self.skip_button.clicked.connect(self.skip_requested)
        self.end_button.clicked.connect(self.end_requested)
        self.setVisible(False)

    def show_prompt(self, index: int, total: int, step, can_repeat: bool):
        """Ask the user to connect the objects of step ``index`` (0-based)."""
        self.setVisible(True)
        self.title.setText(tr("Step {i} of {n}", i=index + 1, n=total))
        lines = [f"<b>{info.label}</b>  →  <span style='font-size:14pt; font-weight:700'>"
                 f"{config.label}</span>" for info, config in step]
        self.text.setText(tr("Please connect:") + "<br>" + "<br>".join(lines))
        self.repeat_button.setVisible(can_repeat)
        self.skip_button.setVisible(True)
        for button in (self.measure_button, self.repeat_button, self.skip_button):
            button.setEnabled(True)
        self.measure_button.setText(tr("▶  Measure"))
        self.measure_button.setFocus()

    def show_countdown(self, seconds: int):
        self.measure_button.setText(tr("▶  Measure now ({s} s)", s=seconds))

    def show_measuring(self, index: int, total: int):
        self.title.setText(tr("Step {i} of {n} – measuring …", i=index + 1, n=total))
        self.measure_button.setEnabled(False)
        self.measure_button.setText(tr("measuring …"))
        self.repeat_button.setVisible(False)
        self.skip_button.setVisible(False)
