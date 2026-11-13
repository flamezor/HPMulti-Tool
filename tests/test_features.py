"""Tests for v0.1.1 features: evaluation, loop distribution, localisation, export columns."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="hpmulti-test-")
os.environ["XDG_DATA_HOME"] = _TMP
os.environ["APPDATA"] = _TMP

from hpmultitool import i18n  # noqa: E402
from hpmultitool.acquisition import Reading  # noqa: E402
from hpmultitool.analysis import (VERDICT_FAIL, VERDICT_PASS, derive, moving_average,  # noqa: E402
                                  platinum_temperature, statistics_of, verdict)
from hpmultitool.export import (DeviceRecord, MeasurementRecord, columns, summary_rows,  # noqa: E402
                                write_csv, write_txt)
from hpmultitool.functions import DeviceConfig, format_reading, preview_value  # noqa: E402
from hpmultitool.instrument import DeviceInfo  # noqa: E402


class EvaluationTests(unittest.TestCase):
    def test_platinum(self):
        self.assertAlmostEqual(platinum_temperature(138.5055, 100), 100.0, places=3)
        self.assertAlmostEqual(platinum_temperature(80.3063, 100), -50.0, places=3)
        self.assertAlmostEqual(platinum_temperature(1000.0, 1000), 0.0, places=6)

    def test_linear_and_tolerance(self):
        cfg = DeviceConfig(function="CURR:DC", conversion="LINEAR", conv_factor=625,
                           conv_offset=-2.5, conv_unit="bar", tolerance="PCT",
                           tol_nominal=5, tol_value=1)
        self.assertAlmostEqual(derive(cfg, 0.012), 5.0)
        self.assertEqual(verdict(cfg, 0.012, 5.0), VERDICT_PASS)
        self.assertEqual(verdict(cfg, 0.013, derive(cfg, 0.013)), VERDICT_FAIL)
        self.assertEqual(verdict(cfg, None, None), VERDICT_FAIL)

    def test_per_length_and_range(self):
        cfg = DeviceConfig(function="FRES", conversion="PER_LENGTH", conv_length=2.0,
                           tolerance="RANGE", tol_low=0.0, tol_high=0.1)
        self.assertAlmostEqual(derive(cfg, 0.15), 0.075)
        self.assertEqual(verdict(cfg, 0.15, 0.075), VERDICT_PASS)

    def test_statistics_and_average(self):
        stats = statistics_of([1, 2, 3, 4], [0, 60, 120, 180])
        self.assertAlmostEqual(stats["drift"], 1.0)
        self.assertEqual(stats["pp"], 3)
        self.assertEqual(moving_average([1, 2, 3, 4], 2), [1, 1.5, 2.5, 3.5])


class LocalisationTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_decimal_separator_follows_language(self):
        cfg = DeviceConfig(function="FRES", dc_resolution="6F")
        i18n.set_language("en")
        self.assertEqual(format_reading(cfg, 108.64463), "108.6446 Ω")
        self.assertEqual(i18n.tr("Ready"), "Ready")
        i18n.set_language("de")
        self.assertEqual(format_reading(cfg, 108.64463), "108,6446 Ω")
        self.assertEqual(i18n.tr("Ready"), "Bereit")
        self.assertEqual(i18n.tr("{n} instrument(s) ready.", n=2), "2 Gerät(e) bereit.")

    def test_preview_uses_range(self):
        self.assertAlmostEqual(preview_value(DeviceConfig(function="VOLT:DC", range=10)),
                               5.432109876)
        self.assertEqual(preview_value(DeviceConfig(), 1.5), 1.5)


class LoopAndExportTests(unittest.TestCase):
    def test_loop_steps_distribution(self):
        from hpmultitool.gui.main_window import build_loop_steps
        a, b = DeviceInfo("A", calibration_message="T034"), DeviceInfo("B", calibration_message="T049")
        steps = build_loop_steps([(a, DeviceConfig()), (b, DeviceConfig())],
                                 ["red", "yellow", "black", "white", "green"])
        self.assertEqual([[c.label for _, c in s] for s in steps],
                         [["red", "yellow"], ["black", "white"], ["green"]])
        self.assertIs(steps[2][0][0], a)

    def test_export_with_steps_and_verdict(self):
        info = DeviceInfo("SIM", identification="HP,34401A,0,1", calibration_message="T034")
        records = []
        for step, (name, value) in enumerate([("red", 0.10), ("yellow", 0.30)], start=1):
            cfg = DeviceConfig(function="FRES", label=name, tolerance="RANGE",
                               tol_low=0, tol_high=0.2)
            v = verdict(cfg, value, None)
            reading = Reading(0, 0, datetime.now().astimezone(), 0.1, value,
                              f"{value:+.8E}", "OK", 1, None, v)
            records.append(DeviceRecord(info, cfg, [reading], step=step))
        record = MeasurementRecord(records, 1, 0, loop=True)
        self.assertIn("Verdict", columns(record))
        rows = summary_rows(record)
        self.assertEqual([r[1] for r in rows], ["red", "yellow"])
        self.assertEqual([r[-1] for r in rows], ["PASS", "FAIL (1/1)"])
        out = Path(_TMP)
        write_csv(record, out / "loop.csv")
        write_txt(record, out / "loop.txt")
        text = (out / "loop.txt").read_text(encoding="utf-8")
        self.assertIn("Summary", text)
        self.assertIn("yellow", text)


if __name__ == "__main__":
    unittest.main()
