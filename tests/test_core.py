"""Hardware-free tests: command generation, formatting, simulated sessions, export, ID write.

Run:  python -m unittest discover -s tests -v
"""

import os
import tempfile
import time
import unittest
from pathlib import Path

# Keep test files out of the user's data directory.
_TMP = tempfile.mkdtemp(prefix="hpmulti-test-")
os.environ["XDG_DATA_HOME"] = _TMP
os.environ["APPDATA"] = _TMP

from hpmultitool.acquisition import Plan, Session  # noqa: E402
from hpmultitool.device_id import validate_id, write_device_id  # noqa: E402
from hpmultitool.export import (DeviceRecord, MeasurementRecord, write_csv,  # noqa: E402
                                write_txt)
from hpmultitool.functions import (FUNCTIONS, MATH_DB, MATH_LIMIT, MATH_NULL,  # noqa: E402
                                   DeviceConfig, configuration_commands, format_reading,
                                   number_text, validate)
from hpmultitool.instrument import decode_scpi_string, discover, encode_scpi_string  # noqa: E402
from hpmultitool.simulator import SimulatedHP34401A  # noqa: E402


class CommandTests(unittest.TestCase):
    def test_every_function_builds_commands(self):
        for key in FUNCTIONS:
            commands = configuration_commands(DeviceConfig(function=key))
            self.assertTrue(commands[0].startswith(f"CONF:{key}"), key)

    def test_dc_fixed_range_and_nplc(self):
        cfg = DeviceConfig(function="VOLT:DC", range=10, dc_resolution="6S",
                           autozero="OFF", high_impedance=True)
        cmds = configuration_commands(cfg)
        self.assertIn("CONF:VOLT:DC 10", cmds)
        self.assertIn("VOLT:DC:NPLC 100", cmds)
        self.assertIn("ZERO:AUTO OFF", cmds)
        self.assertIn("INP:IMP:AUTO ON", cmds)

    def test_fres_and_ratio_have_no_autozero_command(self):
        for key in ("FRES", "VOLT:DC:RAT"):
            cmds = configuration_commands(DeviceConfig(function=key))
            self.assertFalse(any(c.startswith("ZERO:AUTO") for c in cmds), key)
        self.assertIn("VOLT:DC:NPLC 10", configuration_commands(DeviceConfig(function="VOLT:DC:RAT")))

    def test_ac_resolution_and_filter(self):
        cmds = configuration_commands(DeviceConfig(function="VOLT:AC", range=1, ac_resolution="4",
                                                   ac_filter=3))
        self.assertIn("CONF:VOLT:AC 1,0.0001", cmds)
        self.assertIn("DET:BAND 3", cmds)
        cmds = configuration_commands(DeviceConfig(function="CURR:AC", ac_resolution="6"))
        self.assertIn("CONF:CURR:AC DEF,MIN", cmds)

    def test_frequency_gate_and_voltage_range(self):
        cmds = configuration_commands(DeviceConfig(function="FREQ", range=10, gate_time=1.0))
        self.assertIn("FREQ:VOLT:RANG 10", cmds)
        self.assertIn("FREQ:APER 1", cmds)

    def test_math_order(self):
        cfg = DeviceConfig(function="VOLT:DC", math=MATH_NULL, null_offset=0.5)
        cmds = configuration_commands(cfg)
        self.assertLess(cmds.index("CALC:STAT ON"), cmds.index("CALC:NULL:OFFS 0.5"))
        self.assertLess(cmds.index("CONF:VOLT:DC DEF"), cmds.index("CALC:FUNC NULL"))

    def test_math_compatibility(self):
        self.assertTrue(validate(DeviceConfig(function="RES", math=MATH_DB)))
        self.assertFalse(validate(DeviceConfig(function="VOLT:AC", math=MATH_DB)))
        self.assertTrue(validate(DeviceConfig(function="DIOD", math=MATH_LIMIT)))
        self.assertTrue(validate(DeviceConfig(function="RES", math=MATH_LIMIT,
                                              limit_lower=2, limit_upper=1)))


class FormatTests(unittest.TestCase):
    def test_digits_follow_range(self):
        dcv = DeviceConfig(function="VOLT:DC", dc_resolution="4S")
        self.assertEqual(format_reading(dcv, 5.00213), "5.002 V")
        self.assertEqual(number_text(dcv, 5.00213, ","), "5,002")
        fres = DeviceConfig(function="FRES", dc_resolution="6F")
        self.assertEqual(format_reading(fres, 108.644630), "108.6446 Ω")
        self.assertEqual(format_reading(DeviceConfig(function="DIOD"), 0.5873), "587.30 mV")
        self.assertEqual(format_reading(dcv, None), "OVLD")

    def test_scpi_strings(self):
        self.assertEqual(decode_scpi_string('" 5 NOV 1998"'), " 5 NOV 1998")
        self.assertEqual(encode_scpi_string("it's"), "'it''s'")
        self.assertFalse(validate_id("T050"))
        self.assertTrue(validate_id("Prüfmittel"))
        self.assertTrue(validate_id("x" * 41))


class SimulatedSessionTests(unittest.TestCase):
    def _run(self, devices, plan, timeout=20):
        session = Session(devices, plan)
        records = [DeviceRecord(i, c) for i, c in devices]
        session.start()
        deadline = time.monotonic() + timeout
        errors = []
        while (session.running or not session.events.empty()) and time.monotonic() < deadline:
            try:
                event = session.events.get(timeout=0.1)
            except Exception:
                continue
            if event.kind == "reading":
                records[event.slot].readings.append(event.reading)
            elif event.kind == "error":
                errors.append(event.text)
        return session, records, errors

    def test_two_devices_on_common_grid(self):
        devs = discover(simulate=True)
        configs = [DeviceConfig(function="FRES", dc_resolution="4S"),
                   DeviceConfig(function="VOLT:DC", dc_resolution="4F")]
        session, records, errors = self._run(list(zip(devs, configs)), Plan(0.5, 1.5))
        self.assertEqual(errors, [])
        for rec in records:
            self.assertEqual([r.point for r in rec.readings], [0, 1, 2, 3])
        record = MeasurementRecord(records, 0.5, 1.5, session.started_at)
        out = Path(_TMP)
        write_csv(record, out / "a.csv", "de")
        write_csv(record, out / "b.csv", "intl")
        write_txt(record, out / "c.txt")
        text = (out / "a.csv").read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(len(text), 1 + 8)
        self.assertIn(";T034;", text[1] + text[2])
        self.assertIn("Measurement report", (out / "c.txt").read_text(encoding="utf-8"))

    def test_stop_unlimited(self):
        devs = discover(simulate=True)[:1]
        session = Session([(devs[0], DeviceConfig(dc_resolution="4F"))], Plan(0, None))
        session.start()
        time.sleep(1.0)
        session.stop()
        for worker in session.workers:
            worker.join(5)
        self.assertFalse(session.running)

    def test_duplicate_ids_rejected(self):
        devs = discover(simulate=True)
        devs[1].calibration_message = devs[0].calibration_message
        with self.assertRaises(ValueError):
            Session([(d, DeviceConfig()) for d in devs], Plan(1, 1))


class DeviceIdTests(unittest.TestCase):
    def test_write_with_wrong_and_right_code(self):
        info = discover(simulate=True)[1]
        with self.assertRaises(Exception):
            write_device_id(info, "T099", "WRONG1")
        write_device_id(info, "T099", "HP034401", log=lambda _: None)
        meter = SimulatedHP34401A(info.port)
        meter.connect()
        try:
            self.assertEqual(meter.calibration_message(), "T099")
            self.assertTrue(meter.calibration_secured())
        finally:
            meter.close()
        write_device_id(info, "T049", "HP034401", log=lambda _: None)


if __name__ == "__main__":
    unittest.main()
