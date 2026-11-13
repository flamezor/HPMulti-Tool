"""The mouse wheel scrolls the settings and never changes a value (gui.widgets.WheelGuard)."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hpmultitool.functions import DeviceConfig  # noqa: E402
from hpmultitool.gui.device_panel import DeviceSettingsPanel  # noqa: E402
from hpmultitool.gui.widgets import WheelGuard  # noqa: E402


def wheel_down(widget):
    centre = QPointF(widget.rect().center())
    event = QWheelEvent(centre, QPointF(widget.mapToGlobal(centre.toPoint())), QPoint(0, 0),
                        QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)


class WheelGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.guard = WheelGuard(cls.app)
        cls.app.installEventFilter(cls.guard)

    @classmethod
    def tearDownClass(cls):
        cls.app.removeEventFilter(cls.guard)

    def setUp(self):
        self.panel = DeviceSettingsPanel(DeviceConfig(conversion="LINEAR", conv_factor=2.0))
        self.panel.resize(420, 300)   # short, so the settings can scroll
        self.panel.show()
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()

    def test_combo_box_keeps_value_and_page_scrolls(self):
        combo = self.panel.function
        before = combo.currentIndex()
        bar = self.panel.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        wheel_down(combo)
        self.assertEqual(combo.currentIndex(), before)
        self.assertGreater(bar.value(), 0)

    def test_spin_box_keeps_value(self):
        spin = self.panel.conv_factor
        wheel_down(spin)
        self.assertEqual(spin.value(), 2.0)


if __name__ == "__main__":
    unittest.main()
