"""Live page: chart export without a recording and reset per instrument."""

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
from PySide6.QtWidgets import QApplication  # noqa: E402

from hpmultitool import i18n  # noqa: E402


class LivePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        i18n.set_language("en")
        import hpmultitool.gui.main_window as mw
        cls.mw = mw
        cls.original_settings = mw.QSettings
        ini = str(Path(_TMP) / "live.ini")
        mw.QSettings = lambda *a: QSettings(ini, QSettings.IniFormat)

    @classmethod
    def tearDownClass(cls):
        cls.mw.QSettings = cls.original_settings

    def wait(self, condition, timeout=20.0):
        end = time.monotonic() + timeout
        while not condition() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(condition())

    def test_png_without_recording_and_reset_per_instrument(self):
        window = self.mw.MainWindow(simulate=True)
        page = window.live_page
        try:
            self.wait(lambda: len(window.rows) == 2)
            self.assertFalse(page.png_button.isEnabled())      # nothing to save yet
            page.start()
            self.assertTrue(page.png_button.isEnabled())       # no recording needed
            self.wait(lambda: all(len(xs) >= 2 for xs, _ in page.data))

            path = Path(_TMP) / "live_chart.png"
            window._save_path = lambda *a: str(path)
            page.png_button.click()
            self.assertTrue(path.is_file() and path.stat().st_size > 0)

            first, second = page.panels
            reset = next(b for b in first.findChildren(type(page.png_button))
                         if b.text() == i18n.tr("↺ Reset"))
            page.session.devices[0].set_paused(True)          # no new reading in between
            page.session.devices[1].set_paused(True)
            self.app.processEvents()
            time.sleep(0.3)
            page._poll()
            count_second = len(page.data[1][0])
            reset.click()
            self.assertEqual(len(page.data[0][0]), 0)          # chart of this instrument
            self.assertEqual(first.values, [])                 # and its statistics
            self.assertEqual(first.stats.text(), "")
            self.assertEqual(len(page.data[1][0]), count_second)   # other one untouched
            self.assertTrue(second.values)
        finally:
            page.shutdown()
            window.close()


if __name__ == "__main__":
    unittest.main()
