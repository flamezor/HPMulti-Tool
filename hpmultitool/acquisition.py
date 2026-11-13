"""Timed acquisition from one or more instruments.

Each instrument runs in its own thread with its own serial connection.
All threads first connect, verify the instrument identity and apply the
configuration; then they start together on a common time grid
(software synchronisation). Results are passed to the GUI through a
thread-safe queue, so only the GUI thread touches widgets and files.
"""

from __future__ import annotations

import math
import queue
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from .analysis import derive, verdict
from .functions import (DeviceConfig, MATH_LIMIT, MATH_MINMAX, configuration_commands,
                        is_overload, read_timeout)
from .i18n import tr
from .instrument import SERIAL_ERRORS, DeviceInfo, InstrumentError, open_instrument

MAX_CONSECUTIVE_ERRORS = 3


@dataclass
class Reading:
    slot: int
    point: int              # index on the time grid (0, 1, 2, ...)
    timestamp: datetime     # wall-clock time after the instrument answered
    elapsed: float          # seconds since the common start
    value: float | None     # None for overload / error
    raw: str
    status: str             # OK, OVERLOAD, LOW, HIGH, TIMEOUT, ERROR
    samples: int = 1
    derived: float | None = None   # PC-side conversion (analysis.derive)
    verdict: str = ""              # PASS / FAIL against the tolerance, '' = none


@dataclass
class Event:
    kind: str               # status | ready | reading | warning | error | finished
    slot: int
    text: str = ""
    reading: Reading | None = None
    data: dict = field(default_factory=dict)


@dataclass
class Stability:
    """Stop as soon as the last ``window`` readings stay within ``limit``.

    ``limit`` is the allowed spread (max - min) of the window, in percent of
    the mean reading (``relative``) or in the unit of the reading.
    """

    window: int = 10
    limit: float = 0.01
    relative: bool = True

    def stable_mean(self, values) -> float | None:
        """Mean of the window if it is stable, otherwise None."""
        if len(values) < self.window:
            return None
        spread = max(values) - min(values)
        mean = statistics.fmean(values)
        allowed = abs(mean) * self.limit / 100.0 if self.relative else self.limit
        return mean if spread <= allowed else None


@dataclass
class Plan:
    interval: float                 # seconds between points, 0 = as fast as possible
    duration: float | None          # seconds, None = until stopped (maximum with stability)
    stability: Stability | None = None

    def expected_points(self) -> int | None:
        if self.duration is None or self.interval <= 0:
            return None
        return int(math.floor(self.duration / self.interval + 1e-9)) + 1


def apply_configuration(meter, info: DeviceInfo, config: DeviceConfig) -> None:
    """Verify identity, send the configuration and check the error queue."""
    message = meter.calibration_message()
    if message != info.calibration_message:
        raise InstrumentError(tr(
            "Port {port} now reports {found!r} instead of {expected!r}. Please scan for "
            "instruments again.", port=info.port, found=message,
            expected=info.calibration_message))
    meter.write("*CLS")
    for command in configuration_commands(config):
        meter.write(command)
    meter.check_errors(tr("Instrument rejected the configuration"))


def set_mode_only(info: DeviceInfo, config: DeviceConfig) -> None:
    """Switch the instrument into a function and hand it back to the front panel.

    Used for modes without data logging, e.g. continuity or diode test:
    after SYST:LOC the instrument keeps the function and triggers itself.
    """
    meter = open_instrument(info)
    try:
        meter.connect()
        apply_configuration(meter, info, config)
    finally:
        meter.close(local=True)


def read_point(meter, config: DeviceConfig, slot: int, point: int, t0: float) -> Reading:
    """Take one reading (READ?, or INIT/*TRG/FETC? for the software trigger)."""
    try:
        if config.trigger_source == "BUS":
            # Software trigger: arm, trigger, then fetch (READ? would deadlock).
            meter.write("INIT")
            meter.write("*TRG")
            raw = meter.query("FETC?")
        else:
            raw = meter.query("READ?")
    except TimeoutError:
        stamp = datetime.now().astimezone()
        try:
            meter.device_clear()
        except SERIAL_ERRORS:
            pass
        return Reading(slot, point, stamp, time.monotonic() - t0, None,
                       "", "TIMEOUT")
    stamp = datetime.now().astimezone()
    elapsed = time.monotonic() - t0
    try:
        values = [float(part) for part in raw.split(",")]
    except ValueError:
        return Reading(slot, point, stamp, elapsed, None, raw, "ERROR")
    if any(is_overload(v) for v in values):
        return Reading(slot, point, stamp, elapsed, None, raw, "OVERLOAD", len(values),
                       None, verdict(config, None, None))
    value = sum(values) / len(values)
    status = "OK"
    if config.math == MATH_LIMIT:
        if value < config.limit_lower:
            status = "LOW"
        elif value > config.limit_upper:
            status = "HIGH"
    derived = derive(config, value)
    return Reading(slot, point, stamp, elapsed, value, raw, status, len(values),
                   derived, verdict(config, value, derived))


class _DeviceWorker(threading.Thread):
    def __init__(self, session: "Session", slot: int, info: DeviceInfo, config: DeviceConfig):
        super().__init__(name=f"HP34401A-{info.port}", daemon=True)
        self.session = session
        self.slot = slot
        self.info = info
        self.config = config
        self.meter = None

    def interrupt(self):
        """Abort a READ? that is waiting (e.g. for an external trigger)."""
        meter = self.meter
        if meter is not None and meter.connection is not None:
            try:
                meter.connection.cancel_read()
            except (AttributeError, OSError, ValueError):
                pass

    def emit(self, kind, text="", **kwargs):
        self.session.events.put(Event(kind, self.slot, text, **kwargs))

    def run(self):
        meter = self.meter = open_instrument(self.info)
        session = self.session
        try:
            self.emit("status", tr("Connecting …"))
            meter.connect()
            self.emit("status", tr("Configuring …"))
            apply_configuration(meter, self.info, self.config)
            # An external trigger may take arbitrarily long; Stop interrupts the read.
            meter.set_timeout(24 * 3600 if self.config.trigger_source == "EXT"
                              else read_timeout(self.config))
            self.emit("ready", tr("Ready"))
            session.start_barrier.wait(timeout=60)
            self._measure(meter)
            if self.config.math == MATH_MINMAX:
                self._report_minmax(meter)
            self.emit("finished", tr("Done"))
        except threading.BrokenBarrierError:
            self.emit("finished", tr("Cancelled"))
        except SERIAL_ERRORS as error:
            session.start_barrier.abort()
            self.emit("error", str(error))
        except Exception as error:  # never let a thread die silently
            session.start_barrier.abort()
            self.emit("error", f"{type(error).__name__}: {error}")
        finally:
            meter.close(local=True)

    def _measure(self, meter):
        session = self.session
        plan = session.plan
        t0 = session.t0
        interval = plan.interval
        point = 0
        errors_in_row = 0
        window = deque(maxlen=plan.stability.window) if plan.stability else None
        stable = False
        while not session.stop_event.is_set():
            target = t0 + point * interval
            if plan.duration is not None:
                limit = plan.duration + 1e-6
                if (interval > 0 and target - t0 > limit) or (
                        interval <= 0 and time.monotonic() - t0 > limit):
                    break
            delay = target - time.monotonic()
            if delay > 0 and session.stop_event.wait(delay):
                break
            reading = self._read_point(meter, point, t0)
            if session.stop_event.is_set() and reading.status == "TIMEOUT":
                break  # read was interrupted by Stop
            self.emit("reading", reading=reading)
            if window is not None:
                if reading.value is None:
                    window.clear()  # an overload or error restarts the window
                else:
                    window.append(reading.value)
                    mean = plan.stability.stable_mean(window)
                    if mean is not None:
                        stable = True
                        self.emit("stable", tr("stable"),
                                  data={"value": mean, "after": reading.elapsed})
                        break
            if reading.status in ("TIMEOUT", "ERROR"):
                errors_in_row += 1
                if errors_in_row >= MAX_CONSECUTIVE_ERRORS:
                    raise InstrumentError(tr("{n} measurement errors in a row – measurement "
                                             "aborted.",
                                             n=MAX_CONSECUTIVE_ERRORS))
            else:
                errors_in_row = 0
            point += 1
            if interval > 0:
                late = time.monotonic() - (t0 + point * interval)
                if late > 0:
                    skipped = int(late // interval) + 1
                    point += skipped
                    self.emit("warning", tr("Measurement slower than the interval: {n} time "
                                            "slot(s) skipped.", n=skipped))
        if window is not None and not stable:
            self.emit("unstable", tr("not stable"))

    def _read_point(self, meter, point, t0) -> Reading:
        return read_point(meter, self.config, self.slot, point, t0)

    def _report_minmax(self, meter):
        data = {}
        for key, command in (("min", "CALC:AVER:MIN?"), ("max", "CALC:AVER:MAX?"),
                             ("avg", "CALC:AVER:AVER?"), ("count", "CALC:AVER:COUN?")):
            try:
                data[key] = float(meter.query(command))
            except SERIAL_ERRORS:
                data[key] = None
        self.emit("status", tr("Min/max read from the instrument"), data={"instrument_minmax": data})


class Session:
    """One measurement run over the selected devices."""

    def __init__(self, devices: list[tuple[DeviceInfo, DeviceConfig]], plan: Plan):
        if not devices:
            raise ValueError(tr("No instrument selected."))
        labels = [info.label for info, _ in devices]
        if len(set(labels)) != len(labels):
            raise ValueError(tr("Two selected instruments have the same ID. Please assign unique "
                                "IDs in the advanced settings."))
        self.devices = devices
        self.plan = plan
        self.events: queue.Queue[Event] = queue.Queue()
        self.stop_event = threading.Event()
        self.t0 = 0.0
        self.started_at: datetime | None = None
        self.start_barrier = threading.Barrier(len(devices), action=self._set_start)
        self.workers = [_DeviceWorker(self, slot, info, config)
                        for slot, (info, config) in enumerate(devices)]

    def _set_start(self):
        self.t0 = time.monotonic() + 0.1
        self.started_at = datetime.now().astimezone()
        self.events.put(Event("started", -1))

    def start(self):
        for worker in self.workers:
            worker.start()

    def stop(self):
        self.stop_event.set()
        self.start_barrier.abort()
        for worker in self.workers:
            if worker.config.trigger_source == "EXT":
                worker.interrupt()

    @property
    def running(self) -> bool:
        return any(worker.is_alive() for worker in self.workers)
