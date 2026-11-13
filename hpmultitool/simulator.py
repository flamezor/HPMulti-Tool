"""Simulated HP 34401A for development and tests without hardware.

The simulation sits below the real driver: ``SimulatedHP34401A`` replaces
only the serial port, so connect/configure/read run the same code paths
as with a real instrument.
"""

from __future__ import annotations

import math
import random
import re
import threading
import time

from .instrument import HP34401A, DeviceInfo


class _State:
    def __init__(self, message: str, count: int):
        self.message = message
        self.count = count
        self.secured = True
        self.code = "HP034401"
        self.reset()

    def reset(self):
        self.function = "VOLT:DC"
        self.nplc = 10.0
        self.samples = 1
        self.math = "NULL"
        self.math_on = False
        self.null_offset = None
        self.stats = []
        self.errors = []


MAX_READING_TIME = 10.0  # seconds; keeps extreme settings usable in the simulation

# Shared per simulated port, so the state survives reconnects.
_STATES: dict[str, _State] = {}
_STATES_LOCK = threading.Lock()

_BASE_VALUES = {
    "VOLT:DC": 5.00213, "VOLT:AC": 0.70711, "CURR:DC": 0.0123456, "CURR:AC": 0.0213,
    "RES": 108.6446, "FRES": 108.6446, "FREQ": 1000.012, "PER": 0.000999988,
    "VOLT:DC:RAT": 0.4999876, "CONT": 0.35, "DIOD": 0.5873,
}


class _FakeSerial:
    def __init__(self, port: str, state: _State, seed: int):
        self.port = port
        self.state = state
        self.timeout = 3
        self.is_open = True
        self.dsr = True
        self._out = bytearray()
        # Answers that are still being measured: (time when ready, bytes).
        # Like the real instrument, READ? returns at once and the answer
        # arrives after the integration time.
        self._pending: list[tuple[float, bytes]] = []
        self._random = random.Random(seed)
        self._t0 = time.monotonic()

    # pyserial-like API -------------------------------------------------
    def write(self, data: bytes):
        if b"\x03" in data:  # device clear: abort the measurement, drop answers
            self._pending.clear()
            self._out.clear()
        for line in data.decode("ascii").splitlines():
            line = line.strip().replace("\x03", "")
            if line:
                self._handle(line)
        return len(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        self._collect()
        self._out.clear()

    def _collect(self):
        now = time.monotonic()
        while self._pending and self._pending[0][0] <= now:
            self._out.extend(self._pending.pop(0)[1])

    def _wait_for(self, done) -> None:
        """Wait (up to ``timeout``) until ``done()`` is true for the received bytes."""
        deadline = time.monotonic() + (self.timeout if self.timeout is not None else 1e9)
        while True:
            self._collect()
            if done() or time.monotonic() >= deadline:
                return
            time.sleep(0.005)

    def read(self, size=1):
        self._wait_for(lambda: len(self._out) >= size)
        chunk = bytes(self._out[:size])
        del self._out[:size]
        return chunk

    def read_until(self, expected=b"\n", size=None):
        self._wait_for(lambda: expected in self._out)
        index = self._out.index(expected) + len(expected) if expected in self._out \
            else len(self._out)
        line = bytes(self._out[:index])
        del self._out[:index]
        return line

    readline = read_until

    def close(self):
        self.is_open = False

    # command handling ----------------------------------------------------
    def _reply(self, text: str, delay: float = 0.0):
        ready = max([time.monotonic() + delay] + [at for at, _ in self._pending])
        self._pending.append((ready, f"{text}\r\n".encode("ascii")))

    def _value(self) -> float:
        s = self.state
        base = _BASE_VALUES.get(s.function, 1.0)
        t = time.monotonic() - self._t0
        drift = 1 + 2e-5 * math.sin(t / 20.0)
        noise = self._random.gauss(0, 1) * 2e-6 * (10 / max(s.nplc, 0.02)) ** 0.5
        value = base * drift * (1 + noise)
        if s.function == "CONT" and self._random.random() < 0.3:
            value = 9.9e37
        if s.math_on and s.math == "NULL":
            if s.null_offset is None:
                s.null_offset = value
            value -= s.null_offset
        elif s.math_on and s.math in ("DB", "DBM"):
            value = 10 * math.log10(max(value, 1e-12) ** 2 / 600 / 1e-3)
        return value

    def _handle(self, command: str):
        s = self.state
        upper = command.upper()
        if upper == "*IDN?":
            self._reply("HEWLETT-PACKARD,34401A,0,10-5-2")
        elif upper == "CAL:STR?":
            self._reply('"' + s.message.replace('"', '""') + '"')
        elif upper.startswith("CAL:STR "):
            if s.secured:
                s.errors.append('-203,"Command protected"')
            else:
                match = re.match(r"CAL:STR\s+'(.*)'$", command, re.S)
                if match:
                    s.message = match.group(1).replace("''", "'")
        elif upper == "CAL:COUN?":
            self._reply(f"+{s.count}")
        elif upper == "CAL:SEC:STAT?":
            self._reply("1" if s.secured else "0")
        elif upper.startswith("CAL:SEC:STAT "):
            arg = command.split(" ", 1)[1]
            state, _, code = arg.partition(",")
            if code.strip().upper() != s.code:
                s.errors.append('-224,"Illegal parameter value"')
            else:
                s.secured = state.strip().upper() in ("ON", "1")
        elif upper == "SYST:VERS?":
            self._reply("1991.0")
        elif upper == "ROUT:TERM?":
            self._reply("FRON")
        elif upper == "SYST:ERR?":
            self._reply(s.errors.pop(0) if s.errors else '+0,"No error"')
        elif upper == "*CLS":
            s.errors.clear()
        elif upper == "*RST":
            s.reset()
        elif upper == "*TST?":
            self._reply("+0", delay=0.5)
        elif upper.startswith("CONF:"):
            body = upper[5:].split(" ", 1)[0]
            s.function = body if body in _BASE_VALUES else s.function
            s.math_on = False
            s.null_offset = None
            s.stats = []
        elif upper.endswith(":NPLC") or ":NPLC " in upper:
            s.nplc = float(upper.rsplit(" ", 1)[1])
        elif upper.startswith("SAMP:COUN "):
            s.samples = int(float(upper.split(" ", 1)[1]))
        elif upper.startswith("CALC:FUNC "):
            s.math = upper.split(" ", 1)[1]
        elif upper.startswith("CALC:STAT "):
            s.math_on = upper.endswith("ON")
            s.null_offset = None
            s.stats = []
        elif upper.startswith("CALC:NULL:OFFS "):
            s.null_offset = float(upper.split(" ", 1)[1])
        elif upper in ("READ?", "FETC?"):
            if s.function in ("CONT", "DIOD"):
                integration = 0.02
            else:
                integration = s.nplc / 50.0
            values = [self._value() for _ in range(s.samples)]
            s.stats.extend(values)
            self._reply(",".join(f"{v:+.8E}" for v in values),
                        delay=min(MAX_READING_TIME, s.samples * (integration + 0.01)))
        elif upper == "CALC:AVER:MIN?":
            self._reply(f"{min(s.stats, default=0):+.8E}")
        elif upper == "CALC:AVER:MAX?":
            self._reply(f"{max(s.stats, default=0):+.8E}")
        elif upper == "CALC:AVER:AVER?":
            avg = sum(s.stats) / len(s.stats) if s.stats else 0.0
            self._reply(f"{avg:+.8E}")
        elif upper == "CALC:AVER:COUN?":
            self._reply(f"+{len(s.stats)}")
        elif upper.endswith("?"):
            self._reply("+0")
        # every other command is accepted silently


class SimulatedHP34401A(HP34401A):
    """Driver with a simulated serial port."""

    def __init__(self, port: str, message: str = ""):
        super().__init__(port)
        with _STATES_LOCK:
            if port not in _STATES:
                count = 253 if port.endswith("1") else 219
                _STATES[port] = _State(message, count)
            self._state = _STATES[port]

    def _open_serial(self):
        time.sleep(0.05)
        return _FakeSerial(self.port, self._state, seed=hash(self.port) & 0xFFFF)

    def discard_pending_output(self, quiet_time=0.0, max_time=0.0):
        if self.connection is not None:
            self.connection.reset_input_buffer()


SIMULATED = [("SIM-1", "T034"), ("SIM-2", "T049")]


def simulated_devices() -> list[DeviceInfo]:
    devices = []
    for port, message in SIMULATED:
        meter = SimulatedHP34401A(port, message)
        identification = meter.connect()
        info = DeviceInfo(
            port=port, identification=identification,
            calibration_message=meter.calibration_message(),
            calibration_count=meter.calibration_count(),
            firmware=meter.query("SYST:VERS?"), terminals=meter.terminals(),
            usb_serial="SIMULATION", port_description="Simulated instrument", simulated=True,
        )
        meter.close()
        devices.append(info)
    return devices
