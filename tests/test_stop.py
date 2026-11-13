"""Stop aborts a reading in progress instead of waiting for it (simulated instruments)."""

import os
import queue
import tempfile
import threading
import time
import unittest

_TMP = tempfile.mkdtemp(prefix="hpmulti-test-")
os.environ["XDG_DATA_HOME"] = _TMP
os.environ["APPDATA"] = _TMP

from hpmultitool.acquisition import Plan, Session  # noqa: E402
from hpmultitool.functions import DeviceConfig  # noqa: E402
from hpmultitool.instrument import ReadCancelled, discover, open_instrument  # noqa: E402
from hpmultitool.live import LiveSession  # noqa: E402

SLOW = "6S"          # 6½ digits slow = 100 NPLC: about 2 s per reading in the simulation
MAX_STOP_TIME = 1.0  # seconds from Stop until all threads have finished


def events_until(session_events, condition, timeout=15.0):
    events, end = [], time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            event = session_events.get(timeout=0.05)
        except queue.Empty:
            continue
        events.append(event)
        if condition(event):
            return events
    raise AssertionError("expected event did not arrive")


def wait_stopped(session, timeout=10.0):
    start = time.monotonic()
    while session.running and time.monotonic() - start < timeout:
        time.sleep(0.01)
    return time.monotonic() - start


def drain(session_events):
    events = []
    while True:
        try:
            events.append(session_events.get_nowait())
        except queue.Empty:
            return events


class DriverCancelTests(unittest.TestCase):
    def setUp(self):
        self.info = discover(simulate=True)[0]
        self.meter = open_instrument(self.info)
        self.meter.connect()
        self.meter.write("VOLT:DC:NPLC 100")
        self.meter.set_timeout(10)

    def tearDown(self):
        self.meter.close()

    def test_cancel_aborts_waiting_query(self):
        threading.Timer(0.3, self.meter.cancel).start()
        start = time.monotonic()
        with self.assertRaises(ReadCancelled):
            self.meter.query("READ?")
        self.assertLess(time.monotonic() - start, 0.3 + 0.5)

    def test_late_answer_is_dropped_by_device_clear(self):
        threading.Timer(0.2, self.meter.cancel).start()
        with self.assertRaises(ReadCancelled):
            self.meter.query("READ?")
        self.meter.device_clear()
        self.meter.clear_cancel()
        time.sleep(2.2)  # the aborted reading would have been ready now
        self.assertEqual(self.meter.query("*IDN?").split(",")[1], "34401A")

    def test_cut_off_answer_is_not_a_reading(self):
        self.meter.connection._reply("+1.234")
        self.meter.connection._pending[-1] = (0, b"+1.23")  # no line end: answer cut off
        with self.assertRaises(TimeoutError):
            self.meter._read_line(0.3)


class SessionStopTests(unittest.TestCase):
    def test_stop_during_slow_reading(self):
        devices = discover(simulate=True)
        session = Session([(d, DeviceConfig(dc_resolution=SLOW)) for d in devices],
                          Plan(interval=0, duration=None))
        session.start()
        events = events_until(session.events, lambda e: e.kind == "reading")
        time.sleep(0.5)  # now in the middle of the next 2-s reading
        session.stop()
        self.assertLess(wait_stopped(session), MAX_STOP_TIME)
        events += drain(session.events)
        kinds = [e.kind for e in events]
        self.assertNotIn("error", kinds)
        statuses = {e.reading.status for e in events if e.kind == "reading"}
        self.assertEqual(statuses, {"OK"})  # the aborted reading is not reported
        self.assertEqual(kinds.count("finished"), len(devices))

    def test_stop_while_connecting(self):
        devices = discover(simulate=True)
        session = Session([(d, DeviceConfig()) for d in devices], Plan(interval=1, duration=None))
        session.start()
        session.stop()
        self.assertLess(wait_stopped(session), MAX_STOP_TIME + 1)
        self.assertNotIn("error", [e.kind for e in drain(session.events)])

    def test_instrument_usable_after_stop(self):
        devices = discover(simulate=True)
        session = Session([(devices[0], DeviceConfig(dc_resolution=SLOW))],
                          Plan(interval=0, duration=None))
        session.start()
        events_until(session.events, lambda e: e.kind == "started")
        time.sleep(0.5)
        session.stop()
        wait_stopped(session)
        session = Session([(devices[0], DeviceConfig(dc_resolution="4F"))],
                          Plan(interval=0.1, duration=0.5))
        session.start()
        wait_stopped(session)
        readings = [e.reading for e in drain(session.events) if e.kind == "reading"]
        self.assertTrue(readings)
        self.assertTrue(all(r.status == "OK" and 4.9 < r.value < 5.1 for r in readings))


class LiveStopTests(unittest.TestCase):
    def test_stop_during_slow_reading(self):
        devices = discover(simulate=True)
        session = LiveSession([(d, DeviceConfig(dc_resolution=SLOW)) for d in devices])
        session.start()
        events = events_until(session.events, lambda e: e.kind == "reading")
        time.sleep(0.5)
        session.stop()
        self.assertLess(wait_stopped(session), MAX_STOP_TIME)
        events += drain(session.events)
        self.assertNotIn("error", [e.kind for e in events])
        self.assertEqual({e.reading.status for e in events if e.kind == "reading"}, {"OK"})


if __name__ == "__main__":
    unittest.main()
