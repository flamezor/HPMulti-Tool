"""Header bar: title, page switch (Measurement | Live), language, help and theme."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout

from .. import APP_NAME, __version__
from ..i18n import LANGUAGES, language, tr
from .icon import app_icon
from .widgets import DataCombo

PAGE_MEASUREMENT, PAGE_LIVE = 0, 1


class HeaderBar(QFrame):
    page_requested = Signal(int)
    language_selected = Signal(str)
    theme_toggled = Signal()
    help_requested = Signal()

    def __init__(self, simulate: bool):
        super().__init__()
        self.setObjectName("Header")
        layout = QHBoxLayout(self)
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
        if simulate:
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
            button.setChecked(index == PAGE_MEASUREMENT)
            button.clicked.connect(lambda _=False, i=index: self.page_requested.emit(i))
            layout.addWidget(button)
            self.page_buttons.append(button)
        layout.addStretch(1)
        self.language_combo = DataCombo()
        self.language_combo.setMinimumContentsLength(7)
        self.language_combo.set_items(list(LANGUAGES.items()), language())
        self.language_combo.setToolTip(tr("Language"))
        self.language_combo.currentIndexChanged.connect(
            lambda: self.language_selected.emit(self.language_combo.currentData()))
        layout.addWidget(self.language_combo)
        help_button = QToolButton()
        help_button.setText(tr("? Help"))
        help_button.setToolTip(tr("Help on all functions (F1)"))
        help_button.clicked.connect(self.help_requested)
        layout.addWidget(help_button)
        self.theme_button = QToolButton()
        self.theme_button.setToolTip(tr("Light/dark theme"))
        self.theme_button.clicked.connect(self.theme_toggled)
        layout.addWidget(self.theme_button)

    def show_page(self, index: int):
        """Check the button of the page that is shown."""
        for i, button in enumerate(self.page_buttons):
            button.setChecked(i == index)

    def reset_language(self):
        self.language_combo.select_data(language())

    def set_theme(self, theme: str):
        self.theme_button.setText("☀" if theme == "dark" else "☾")
