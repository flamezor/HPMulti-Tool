"""Tests for v0.1.2: measure until stable, test profiles, clock axis."""

import os
import tempfile
import time
import unittest

_TMP = tempfile.mkdtemp(prefix="hpmulti-test-")
os.environ["XDG_DATA_HOME"] = _TMP
os.environ["APPDATA"] = _TMP

from hpmultitool.acquisition import Plan, Session, Stability  # noqa: E402
from hpmultitool.export import DeviceRecord, MeasurementRecord, summary_rows  # noqa: E402
from hpmultitool.functions import DeviceConfig  # noqa: E402
from hpmultitool.instrument import DeviceInfo, discover  # noqa: E402
from hpmultitool.profiles import (assign_configs, delete_profile, list_profiles,  # noqa: E402
                                  load_profile, save_profile)


class StabilityTests(unittest.TestCase):
    def test_criterion(self):
        st = Stability(window=3, limit=0.01, relative=True)
        self.assertIsNone(st.stable_mean([100.0, 100.0]))
        self.assertAlmostEqual(st.stable_mean([100.0, 100.005, 100.009]), 100.00466, places=4)
        self.assertIsNone(st.stable_mean([100.0, 100.02, 100.0]))
        self.assertEqual(Stability(3, 0.5, False).stable_mean([1.0, 1.2, 1.4]), 1.2)

    def _run(self, stability, duration):
        devs = discover(simulate=True)
        configs = [DeviceConfig(function="FRES", dc_resolution="4F"),
                   DeviceConfig(function="VOLT:DC", dc_resolution="4F")]
        session = Session(list(zip(devs, configs)), Plan(0.05, duration, stability))
        session.start()
        events = []
        deadline = time.monotonic() + 20
        while (session.running or not session.events.empty()) and time.monotonic() < deadline:
            try:
                events.append(session.events.get(timeout=0.1))
            except Exception:
                pass
        return events

    def test_simulated_devices_become_stable(self):
        events = self._run(Stability(5, 0.01, True), 10)
        stable = [e for e in events if e.kind == "stable"]
        self.assertEqual(sorted(e.slot for e in stable), [0, 1])
        readings = [e for e in events if e.kind == "reading" and e.slot == 0]
        self.assertGreaterEqual(len(readings), 5)
        self.assertLess(len(readings), 50)  # stopped early, not after 10 s

    def test_unstable_reported(self):
        events = self._run(Stability(5, 0.0, False), 0.5)  # zero spread is impossible
        self.assertEqual(sorted(e.slot for e in events if e.kind == "unstable"), [0, 1])

    def test_verdict_uses_final_value(self):
        info = DeviceInfo("SIM", calibration_message="T034")
        cfg = DeviceConfig(function="FRES", label="red", tolerance="RANGE", tol_low=0,
                           tol_high=1)
        rec = DeviceRecord(info, cfg, readings=[object()], stability_used=True,
                           stable_value=0.5, stable_after=3.2)
        self.assertEqual(rec.verdict()[0], "PASS")
        rec.stable_value = None
        self.assertEqual(rec.verdict()[0], "FAIL")


class ProfileTests(unittest.TestCase):
    def test_round_trip_and_assignment(self):
        cfg_a = DeviceConfig(function="FRES", label="x", samples=4)
        cfg_b = DeviceConfig(function="VOLT:AC")
        path = save_profile("Sensor cable / 6", {"mode": "loop", "duration": 0,
                                                 "objects": ["red", "yellow"]},
                            [{"id": "T034", "use": True, "config": cfg_a.to_dict()},
                             {"id": "T049", "use": False, "config": cfg_b.to_dict()}])
        self.assertIn("Sensor cable / 6", [name for name, _ in list_profiles()])
        profile = load_profile(path)
        self.assertEqual(profile["plan"]["objects"], ["red", "yellow"])
        self.assertEqual(profile["devices"][0]["config"].samples, 4)
        # same ID first, then by order
        mapping = assign_configs(profile["devices"], ["T999", "T034"])
        self.assertEqual(mapping["T034"]["id"], "T034")
        self.assertEqual(mapping["T999"]["id"], "T049")
        delete_profile(path)
        self.assertNotIn("Sensor cable / 6", [name for name, _ in list_profiles()])

    def test_summary_has_final_value(self):
        info = DeviceInfo("SIM", calibration_message="T034")
        rec = DeviceRecord(info, DeviceConfig(function="FRES", label="red"), readings=[],
                           stability_used=True, stable_value=108.6446, stable_after=4.25)
        row = summary_rows(MeasurementRecord([rec], 1, 60))[0]
        self.assertIn("108", row[9])
        self.assertTrue(row[10].endswith("s"))


class ClockAxisTests(unittest.TestCase):
    def test_ticks_are_whole_seconds(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from hpmultitool.gui.plotting import ClockAxis
        axis = ClockAxis(orientation="bottom")
        start = time.mktime((2026, 11, 13, 8, 0, 3, 0, 0, -1)) + 0.4
        levels = axis.tickValues(start, start + 47, 600)
        major = levels[0][1]
        self.assertTrue(all(abs(v - round(v)) < 1e-6 for v in major))
        labels = axis.tickStrings(major, 1, levels[0][0])
        self.assertTrue(all(len(text) == 8 and text.count(":") == 2 for text in labels))
        self.assertEqual(len(set(labels)), len(labels))


if __name__ == "__main__":
    unittest.main()
