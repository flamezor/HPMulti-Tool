"""Help window: topic list and HTML pages in the active language."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QListWidget, QTextBrowser,
                               QVBoxLayout)

from ..i18n import language, tr
from .help_content import HELP


class HelpDialog(QDialog):
    def __init__(self, parent=None, topic: int = 0):
        super().__init__(parent)
        self.setWindowTitle(tr("Help"))
        self.resize(980, 700)
        pages = HELP.get(language(), HELP["en"])
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.topics = QListWidget()
        self.topics.setFixedWidth(240)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        for title, _ in pages:
            self.topics.addItem(title)
        self.topics.currentRowChanged.connect(
            lambda index: self.browser.setHtml(pages[index][1]) if index >= 0 else None)
        row.addWidget(self.topics)
        row.addWidget(self.browser, 1)
        layout.addLayout(row, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.topics.setCurrentRow(topic)
        self.topics.setFocus(Qt.OtherFocusReason)
