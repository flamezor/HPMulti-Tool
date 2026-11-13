"""Small reusable widgets."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRunnable, Qt, Signal
from PySide6.QtWidgets import (QAbstractScrollArea, QAbstractSpinBox, QApplication, QComboBox,
                               QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget)


class WheelGuard(QObject):
    """The mouse wheel scrolls the page and never changes a selection or number field.

    Installed once on the application. Without it, scrolling through the settings
    changes every combo or spin box that passes under the mouse pointer. Values are
    changed by clicking (drop-down list) or with the keyboard.
    """

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming
        if event.type() == QEvent.Wheel and isinstance(obj, (QComboBox, QAbstractSpinBox)):
            # Scroll the surrounding scroll area instead. Qt does not pass a forwarded wheel
            # event on to parent widgets, so it goes straight to the scroll bar.
            area = obj.parentWidget()
            while area is not None and not isinstance(area, QAbstractScrollArea):
                area = area.parentWidget()
            if area is not None:
                QApplication.sendEvent(area.verticalScrollBar(), event)
            return True
        return False


class Card(QFrame):
    """Rounded surface with an optional title."""

    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(16, 14, 16, 16)
        self.outer.setSpacing(10)
        if title:
            head = QLabel(title)
            head.setObjectName("CardTitle")
            self.outer.addWidget(head)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Muted")
            sub.setWordWrap(True)
            self.outer.addWidget(sub)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        self.outer.addLayout(self.body)


def section_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("SectionLabel")
    return label


def muted(text: str, wrap: bool = True) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Muted")
    label.setWordWrap(wrap)
    return label


def hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    return label


class DataCombo(QComboBox):
    """Combo box whose items carry data; selection by data value."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Do not let long item texts force the side panels wider.
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(12)
        self.view().setTextElideMode(Qt.ElideNone)

    def set_items(self, items, current=None):
        self.blockSignals(True)
        self.clear()
        for data, text in items:
            self.addItem(text, data)
        self.blockSignals(False)
        if current is not None and not self.select_data(current) and self.count():
            self.setCurrentIndex(0)

    def set_grouped_items(self, groups, current=None):
        """Items under bold, non-selectable headings: groups = [(heading, [(data, text), …])]."""
        self.blockSignals(True)
        self.clear()
        model = self.model()
        for heading, items in groups:
            self.addItem(heading)
            header = model.item(self.count() - 1)
            header.setFlags(Qt.NoItemFlags)     # cannot be selected, skipped by the keyboard
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            for data, text in items:
                self.addItem(text, data)
        self.blockSignals(False)
        if current is None or not self.select_data(current):
            first = next((i for i in range(self.count()) if self.itemData(i) is not None), -1)
            self.setCurrentIndex(first)

    def select_data(self, data) -> bool:
        for index in range(self.count()):
            if self.itemData(index) == data:
                self.setCurrentIndex(index)
                return True
        return False


class StatusDot(QLabel):
    COLORS = {"idle": "#8b98a5", "ok": "#34d399", "busy": "#fbbf24", "error": "#f87171"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.set_state("idle")

    def set_state(self, state: str):
        self.setStyleSheet(f"background:{self.COLORS.get(state, '#8b98a5')}; border-radius:5px;")


class FormRow(QWidget):
    """Label above a field; hides together with its field."""

    def __init__(self, label: str, field: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.label = QLabel(label)
        self.label.setObjectName("Muted")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        layout.addWidget(field)
        self.field = field


def hbox(*widgets, spacing=8, stretch_last=False) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    for widget in widgets:
        if widget is None:
            layout.addStretch(1)
        else:
            layout.addWidget(widget)
    return layout


def expanding(widget: QWidget) -> QWidget:
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return widget


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    """Run a blocking function in the Qt thread pool."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = TaskSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as error:  # reported to the GUI
            self.signals.failed.emit(str(error) or type(error).__name__)
        else:
            self.signals.done.emit(result)
