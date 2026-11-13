"""Measurement result x̄ ± u: statistics, Student t, rounding and the 34401A specifications."""

import unittest
from decimal import Decimal

from hpmultitool import i18n
from hpmultitool.analysis import (MIN_READINGS, evaluate, result_text, round_significant,
                                  round_to, student_t)
from hpmultitool.functions import DeviceConfig
from hpmultitool.specs import instrument_error


class StudentTests(unittest.TestCase):
    # Table "Vertrauensgrenzen" of the lecture (t for n readings).
    TABLE = {2: (1.84, 12.71, 63.66), 3: (1.32, 4.30, 9.93), 5: (1.15, 2.78, 4.60),
             10: (1.06, 2.26, 3.25), 20: (1.03, 2.09, 2.86), 100: (1.00, 1.98, 2.63)}

    def test_matches_table(self):
        for n, expected in self.TABLE.items():
            for confidence, t in zip((68.27, 95.0, 99.0), expected):
                with self.subTest(n=n, confidence=confidence):
                    self.assertAlmostEqual(student_t(confidence, n), t, delta=0.01)

    def test_single_reading_has_no_t(self):
        self.assertIsNone(student_t(95.0, 1))


class RoundingTests(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")

    def test_two_significant_digits(self):
        self.assertEqual(round_significant(2.624)[0], Decimal("2.6"))
        self.assertEqual(round_significant(0.0689)[0], Decimal("0.069"))
        self.assertEqual(round_significant(9.96)[0], Decimal("10"))

    def test_ties_to_even(self):
        self.assertEqual(round_to(4.135, -2), Decimal("4.14"))
        self.assertEqual(round_to(4.125, -2), Decimal("4.12"))

    def test_result_text(self):
        # Examples from the lab script "Fehler- und Ausgleichsrechnung".
        self.assertEqual(result_text(83.62, 2.624, "Ω"), "(83.6 ± 2.6) Ω")
        self.assertEqual(result_text(90.4671, 1.1, "s"), "(90.5 ± 1.1) s")
        self.assertEqual(result_text(9.80134, 0.0689, "m/s²"), "(9.801 ± 0.069) m/s²")
        self.assertEqual(result_text(0.0123456, 1.2e-6, "A"), "(12.3456 ± 0.0012) mA")

    def test_german_decimal_comma(self):
        i18n.set_language("de")
        try:
            self.assertEqual(result_text(83.62, 2.624, "Ω"), "(83,6 ± 2,6) Ω")
        finally:
            i18n.set_language("en")


class EvaluationTests(unittest.TestCase):
    def test_series_from_lecture(self):
        cfg = DeviceConfig(function="FRES", range=100, confidence=68.27)
        ev = evaluate([12, 8, 20, 15, 16], cfg)
        self.assertAlmostEqual(ev.mean, 14.2)
        self.assertAlmostEqual(ev.s, 4.494, places=3)
        self.assertAlmostEqual(ev.sem, 4.494 / 5 ** 0.5, places=3)
        self.assertAlmostEqual(ev.t, 1.14, delta=0.01)
        self.assertAlmostEqual(ev.u, ev.t * ev.sem + ev.h)
        self.assertTrue(ev.valid)

    def test_too_few_readings(self):
        cfg = DeviceConfig(function="VOLT:DC", range=10)
        ev = evaluate([5.0, 5.0001, 5.0002], cfg)
        self.assertFalse(ev.valid)
        self.assertEqual(ev.u, ev.h)          # only the instrument error
        self.assertEqual(MIN_READINGS, 4)
        self.assertTrue(evaluate([5.0] * 4, cfg).valid)

    def test_conversion_scales_uncertainty(self):
        cfg = DeviceConfig(function="CURR:DC", range=0.1, conversion="LINEAR", conv_factor=625,
                           conv_offset=-2.5, conv_unit="bar")
        ev = evaluate([0.012, 0.0121, 0.0119, 0.012], cfg)
        converted = ev.converted(cfg)
        self.assertAlmostEqual(converted.mean, 625 * ev.mean - 2.5)
        self.assertAlmostEqual(converted.u, 625 * ev.u)

    def test_no_readings(self):
        ev = evaluate([], DeviceConfig())
        self.assertEqual(ev.n, 0)
        self.assertIsNone(ev.u)

    def test_uncertainty_switched_off(self):
        cfg = DeviceConfig(function="VOLT:DC", range=10, uncertainty=False,
                           conversion="LINEAR", conv_factor=2.0)
        ev = evaluate([5.0, 5.0002], cfg)    # even with fewer than 4 readings
        self.assertTrue(ev.valid)
        self.assertAlmostEqual(ev.mean, 5.0001)
        self.assertIsNotNone(ev.s)
        self.assertIsNotNone(ev.sem)
        for value in (ev.t, ev.random, ev.h, ev.u):
            self.assertIsNone(value)
        self.assertFalse(ev.converted(cfg).with_uncertainty)
        self.assertEqual(ev.notes, [])

    def test_uncertainty_switched_off_in_export(self):
        from datetime import datetime
        from hpmultitool.acquisition import Reading
        from hpmultitool.instrument import DeviceInfo
        from hpmultitool.export import (DeviceRecord, MeasurementRecord, SUMMARY_HEADERS,
                                        UNCERTAINTY_COLUMNS, evaluation_lines, summary_columns,
                                        summary_rows)
        i18n.set_language("en")
        info = DeviceInfo("SIM", calibration_message="T034")
        readings = [Reading(0, i, datetime.now().astimezone(), i, v, f"{v:+.8E}", "OK")
                    for i, v in enumerate([5.0, 5.0001, 5.0002, 5.0001])]
        off = DeviceRecord(info, DeviceConfig(function="VOLT:DC", uncertainty=False), readings)
        rows = summary_rows(MeasurementRecord([off], 1, 60))
        for column in UNCERTAINTY_COLUMNS:
            self.assertEqual(rows[0][column], "")
            self.assertNotIn(column, summary_columns(rows))
        self.assertEqual(SUMMARY_HEADERS[UNCERTAINTY_COLUMNS[0]], "t")
        self.assertIn("not calculated", dict(evaluation_lines(off))["Uncertainty u"])
        self.assertNotIn("Student t", dict(evaluation_lines(off)))
        # mixed: columns stay when one record has an uncertainty
        on = DeviceRecord(info, DeviceConfig(function="VOLT:DC"), readings, step=2)
        rows = summary_rows(MeasurementRecord([off, on], 1, 60))
        self.assertTrue(all(c in summary_columns(rows) for c in UNCERTAINTY_COLUMNS))


class SpecificationTests(unittest.TestCase):
    """Values from the accuracy tables, chapter 8 of the user's guide."""

    def h(self, value, **settings):
        error = instrument_error(DeviceConfig(**settings), value)
        return None if error is None else error.value

    def test_dc_voltage(self):
        # 10 V range, 1 year: 0.0035 % of reading + 0.0005 % of range
        self.assertAlmostEqual(self.h(5.0, function="VOLT:DC", range=10), 225e-6)
        self.assertAlmostEqual(self.h(5.0, function="VOLT:DC", range=10, spec_period="24h"),
                               (0.0015 * 5 + 0.0004 * 10) / 100)
        # autorange: 5 V → 10 V range
        self.assertAlmostEqual(self.h(5.0, function="VOLT:DC"), 225e-6)

    def test_noise_error_below_6_digits(self):
        # 4½ digits (0.02 NPLC): + 0.01 % of range + 20 µV
        self.assertAlmostEqual(self.h(5.0, function="VOLT:DC", range=10, dc_resolution="4F"),
                               225e-6 + 0.001 + 20e-6)

    def test_resistance(self):
        # 4-wire, 1 kΩ range, 1 year: 0.010 % + 0.001 %
        self.assertAlmostEqual(self.h(500.0, function="FRES", range=1000),
                               (0.010 * 500 + 0.001 * 1000) / 100)
        # 2-wire without null: + 0.2 Ω
        self.assertAlmostEqual(self.h(500.0, function="RES", range=1000),
                               (0.010 * 500 + 0.001 * 1000) / 100 + 0.2)

    def test_ac_voltage(self):
        # 1 V range, 50 Hz, medium filter: (0.06 + 0.06) % of reading + 0.03 % of range
        self.assertAlmostEqual(self.h(0.7071, function="VOLT:AC", range=1),
                               (0.12 * 0.7071 + 0.03 * 1) / 100)
        # fast filter at 15 Hz is not specified
        self.assertIsNone(self.h(0.7071, function="VOLT:AC", range=1, ac_filter=200,
                                 signal_frequency=15))

    def test_frequency(self):
        # 1 kHz, 5½ digits (100 ms gate), 1 year: 0.01 % of reading
        self.assertAlmostEqual(self.h(1000.0, function="FREQ", gate_time=0.1), 0.1)
        # 50 Hz with 4½ digits: + 0.21 %
        self.assertAlmostEqual(self.h(50.0, function="FREQ", gate_time=0.01),
                               (0.01 + 0.21) * 50 / 100)

    def test_not_specified(self):
        self.assertIsNone(self.h(0.5, function="VOLT:DC:RAT"))
        self.assertIsNone(self.h(10.0, function="VOLT:AC", math="DBM"))


if __name__ == "__main__":
    unittest.main()
