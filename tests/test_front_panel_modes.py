"""Continuity and diode test: not logged in the measurement plan, but can be switched to."""

import os
import tempfile
import time
import unittest
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="hpmulti-test-")
os.environ["XDG_DATA_HOME"] = _TMP
os.environ["APPDATA"] = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from hpmultitool import i18n  # noqa: E402
from hpmultitool.functions import DeviceConfig, is_loggable  # noqa: E402


class LoggableTests(unittest.TestCase):
    def test_front_panel_modes(self):
        self.assertFalse(is_loggable(DeviceConfig(function="CONT")))
        self.assertFalse(is_loggable(DeviceConfig(function="DIOD")))
        self.assertTrue(is_loggable(DeviceConfig(function="RES")))


class MeasurementPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        i18n.set_language("en")
        import hpmultitool.gui.main_window as mw
        cls.mw = mw
        cls.original_settings = mw.QSettings
        ini = str(Path(_TMP) / "settings.ini")
        mw.QSettings = lambda *a: QSettings(ini, QSettings.IniFormat)
        cls.messages = []
        cls.original_information = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *a: cls.messages.append(a[2]) or 0)

    @classmethod
    def tearDownClass(cls):
        cls.mw.QSettings = cls.original_settings
        QMessageBox.information = cls.original_information

    def wait(self, condition, timeout=20.0):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(condition())

    def test_continuity_blocks_start_but_can_be_switched_to(self):
        window = self.mw.MainWindow(simulate=True)
        try:
            self.wait(lambda: len(window.rows) == 2)
            panel = window.panels[window.rows[0].info.port]
            self.assertTrue(window.plan_card.start_button.isEnabled())

            panel.function.select_data("CONT")   # user selects continuity
            self.app.processEvents()
            self.assertFalse(window.plan_card.start_button.isEnabled())
            self.assertIn("not logged", window.plan_card.info.text())
            self.assertIn("Continuity test", window.plan_card.info.text())
            # only what matters for the front-panel mode is shown, the switch button moves up
            for card in (panel.card_math, panel.card_evaluation, panel.card_trigger):
                self.assertTrue(card.isHidden())
            self.assertTrue(panel.display_on.isHidden())
            self.assertEqual(panel._root.indexOf(panel.card_mode), 1)
            self.assertIn("DISP ON", panel.scpi_preview.text())

            window.start_measurement()            # e.g. via keyboard: nothing starts
            self.assertFalse(window.runner.busy)
            self.assertTrue(self.messages and "not logged" in self.messages[-1])

            window.apply_mode(window.rows[0].info)  # still available
            self.wait(lambda: panel.widget().isEnabled())

            panel.function.select_data("RES")
            self.app.processEvents()
            self.assertTrue(window.plan_card.start_button.isEnabled())
            for card in (panel.card_math, panel.card_evaluation, panel.card_trigger):
                self.assertFalse(card.isHidden())
            self.assertEqual(panel._root.indexOf(panel.card_mode), panel._root.count() - 2)
        finally:
            window.shutdown()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()
