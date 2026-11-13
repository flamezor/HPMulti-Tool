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
from hpmultitool.analysis import derive, statistics_of  # noqa: E402
from hpmultitool.export import (DeviceRecord, MeasurementRecord, columns, summary_rows,  # noqa: E402
                                write_csv, write_txt)
from hpmultitool.functions import DeviceConfig, format_reading, preview_value  # noqa: E402
from hpmultitool.instrument import DeviceInfo  # noqa: E402


class ConversionTests(unittest.TestCase):
    def test_linear(self):
        cfg = DeviceConfig(function="CURR:DC", conversion="LINEAR", conv_factor=625,
                           conv_offset=-2.5, conv_unit="bar")
        self.assertAlmostEqual(derive(cfg, 0.012), 5.0)
        self.assertIsNone(derive(cfg, None))

    def test_per_length(self):
        cfg = DeviceConfig(function="FRES", conversion="PER_LENGTH", conv_length=2.0)
        self.assertAlmostEqual(derive(cfg, 0.15), 0.075)

    def test_running_statistics(self):
        stats = statistics_of([1, 2, 3, 4])
        self.assertEqual((stats["min"], stats["max"], stats["count"]), (1, 4, 4))
        self.assertAlmostEqual(stats["mean"], 2.5)


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
        from hpmultitool.series import build_loop_steps
        a, b = DeviceInfo("A", calibration_message="T034"), DeviceInfo("B", calibration_message="T049")
        steps = build_loop_steps([(a, DeviceConfig()), (b, DeviceConfig())],
                                 ["red", "yellow", "black", "white", "green"])
        self.assertEqual([[c.label for _, c in s] for s in steps],
                         [["red", "yellow"], ["black", "white"], ["green"]])
        self.assertIs(steps[2][0][0], a)

    def test_export_with_steps_and_result(self):
        info = DeviceInfo("SIM", identification="HP,34401A,0,1", calibration_message="T034")
        records = []
        for step, (name, values) in enumerate([("red", [100.1, 100.3, 100.2, 100.4, 100.0]),
                                               ("yellow", [99.0, 99.2])], start=1):
            cfg = DeviceConfig(function="FRES", label=name, range=100)
            readings = [Reading(0, i, datetime.now().astimezone(), 0.1 * i, v, f"{v:+.8E}",
                                "OK") for i, v in enumerate(values)]
            records.append(DeviceRecord(info, cfg, readings, step=step))
        record = MeasurementRecord(records, 1, 0, loop=True)
        self.assertNotIn("Verdict", columns(record))
        rows = summary_rows(record)
        self.assertEqual([r[1] for r in rows], ["red", "yellow"])
        self.assertEqual([r[3] for r in rows], ["5", "2"])           # n
        self.assertTrue(rows[0][10].startswith("(100."))            # result x̄ ± u
        self.assertEqual(rows[0][-1], "")                           # valid: no note
        self.assertEqual(rows[1][-1], "n < 4")
        out = Path(_TMP)
        write_csv(record, out / "loop.csv")
        write_txt(record, out / "loop.txt")
        text = (out / "loop.txt").read_text(encoding="utf-8")
        self.assertIn("Summary", text)
        self.assertIn("Uncertainty u", text)
        self.assertIn("(not valid)", text)


if __name__ == "__main__":
    unittest.main()
