"""Tests for the live mode (v0.1.3) with simulated instruments."""

import os
import tempfile
import time
import unittest

os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="hpmulti-test-")

from hpmultitool.functions import DeviceConfig  # noqa: E402
from hpmultitool.instrument import discover  # noqa: E402
from hpmultitool.live import LiveSession  # noqa: E402


class LiveTests(unittest.TestCase):
    def setUp(self):
        devices = discover(simulate=True)
        self.session = LiveSession([(d, DeviceConfig(dc_resolution="4F")) for d in devices], 0.05)
        self.session.start()

    def tearDown(self):
        self.session.stop()
        for device in self.session.devices:
            device.join(5)
        self.assertFalse(self.session.running)

    def drain(self, seconds):
        events, end = [], time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                events.append(self.session.events.get(timeout=0.05))
            except Exception:
                pass
        return events

    def readings(self, events, slot):
        return [e.reading for e in events if e.kind == "reading" and e.slot == slot]

    def test_readings_and_config_change(self):
        events = self.drain(1.5)
        self.assertTrue(self.readings(events, 0))
        self.assertTrue(self.readings(events, 1))
        self.session.devices[0].set_config(DeviceConfig(function="FRES", dc_resolution="4F"))
        events = self.drain(1.5)
        configured = [e for e in events if e.kind == "configured" and e.slot == 0]
        self.assertEqual(configured[-1].data["config"].function, "FRES")
        after = [r.value for r in self.readings(events[events.index(configured[-1]):], 0)]
        self.assertTrue(after and all(100 < v < 120 for v in after))

    def test_pause_and_resume(self):
        self.drain(0.8)
        self.session.devices[1].set_paused(True)
        self.drain(0.5)
        self.assertFalse(self.readings(self.drain(0.8), 1))
        self.session.devices[1].set_paused(False)
        self.assertTrue(self.readings(self.drain(1.0), 1))

    def test_invalid_config_is_rejected(self):
        self.drain(0.8)
        bad = DeviceConfig(function="DIOD")
        bad.math = "NULL"
        self.session.devices[0].set_config(bad)
        events = self.drain(2.5)  # the old configuration is sent again first
        self.assertTrue(any(e.kind == "warning" and e.slot == 0 for e in events))
        self.assertTrue(self.readings(events, 0))  # still measuring with the old settings
        self.assertTrue(self.session.devices[0].is_alive())


if __name__ == "__main__":
    unittest.main()
