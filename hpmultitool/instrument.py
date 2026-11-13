"""RS-232 driver and discovery for HP 34401A multimeters.

Serial settings follow the 34401A factory RS-232 setup: 9600 baud,
7 data bits, even parity, 2 stop bits, DTR/DSR handshaking.

Handshake: after receiving a command the 34401A drops its DTR line (our
DSR) for roughly 20-400 ms while it executes. Characters sent during that
time are lost. Windows can pace output on DSR in the driver, Linux cannot,
so ``_raw_write`` implements the handshake in software on both platforms:
wait until DSR is asserted, send, then wait for the busy pulse to end.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import serial
from serial.tools import list_ports

from .i18n import tr

SERIAL_ERRORS = (serial.SerialException, OSError, TimeoutError, RuntimeError, ValueError)


class InstrumentError(RuntimeError):
    """The instrument reported an error or answered unexpectedly."""


class ReadCancelled(TimeoutError):
    """Waiting for an answer was aborted with ``HP34401A.cancel()``."""


def decode_scpi_string(response: str) -> str:
    """Remove SCPI string quotes; keep significant spaces inside the string."""
    if len(response) < 2 or response[0] not in ('"', "'") or response[-1] != response[0]:
        raise InstrumentError(f"Unexpected string response: {response!r}")
    quote = response[0]
    return response[1:-1].replace(quote * 2, quote)


def encode_scpi_string(text: str) -> str:
    """Quote text as an SCPI string parameter."""
    return "'" + text.replace("'", "''") + "'"


class HP34401A:
    """One RS-232 connection to an HP 34401A."""

    BAUDRATE = 9600

    def __init__(self, port: str):
        self.port = port
        self.connection: serial.Serial | None = None
        self._lock = threading.RLock()
        self._cancel = threading.Event()

    # -- connection -------------------------------------------------------
    def _open_serial(self):
        return serial.Serial(
            port=self.port,
            baudrate=self.BAUDRATE,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            timeout=3,
            write_timeout=3,
            dsrdtr=True,
            rtscts=False,
            xonxoff=False,
        )

    @property
    def is_open(self) -> bool:
        return self.connection is not None and self.connection.is_open

    def connect(self, attempts: int = 3) -> str:
        """Open the port, enter remote mode and return the *IDN? string."""
        self.connection = self._open_serial()
        try:
            time.sleep(0.3)
            # Nothing connected (or instrument off / set to HP-IB): DSR stays low.
            self._wait_ready(timeout=1.5)
            self.discard_pending_output()
            last_error: Exception | None = None
            for _ in range(attempts):
                try:
                    self.write("SYST:REM")
                    identification = self.identify()
                    self.write("*CLS")  # drop -410 "Query INTERRUPTED" leftovers
                    return identification
                except (TimeoutError, InstrumentError) as error:
                    last_error = error
                    self.discard_pending_output()
            raise TimeoutError(tr("{port}: no valid answer from an HP 34401A ({error})",
                                  port=self.port, error=last_error))
        except Exception:
            self._close_port()
            raise

    def close(self, local: bool = True) -> None:
        """Return the instrument to front-panel (local) mode and close the port."""
        if self.connection is None:
            return
        try:
            if local and self.connection.is_open:
                self.write("SYST:LOC")
                self.connection.flush()
        except SERIAL_ERRORS:
            pass
        finally:
            self._close_port()

    def _close_port(self):
        try:
            if self.connection is not None:
                self.connection.close()
        finally:
            self.connection = None

    def discard_pending_output(self, quiet_time: float = 0.25, max_time: float = 3.0) -> None:
        """Drop bytes until the line has been quiet for ``quiet_time``."""
        conn = self._require_open()
        previous = conn.timeout
        conn.timeout = quiet_time
        deadline = time.monotonic() + max_time
        try:
            conn.reset_input_buffer()
            while conn.read(256):
                if time.monotonic() > deadline:
                    raise InstrumentError(f"{self.port} is sending continuous data.")
        finally:
            conn.timeout = previous

    def _require_open(self) -> serial.Serial:
        if not self.is_open:
            raise RuntimeError("Serial connection is not open.")
        return self.connection

    # -- I/O ----------------------------------------------------------------
    READY_TIMEOUT = 5.0     # max. time the instrument may stay busy
    BUSY_DETECT_TIME = 0.05  # DSR drops 7-25 ms after the command was sent

    def _wait_ready(self, timeout: float | None = None) -> None:
        """Block until the instrument asserts DSR (ready to receive)."""
        conn = self._require_open()
        deadline = time.monotonic() + (timeout or self.READY_TIMEOUT)
        while not conn.dsr:
            if time.monotonic() > deadline:
                raise TimeoutError(tr(
                    "{port}: instrument not ready (DSR low). Is it switched on and set to RS-232?", port=self.port))
            time.sleep(0.002)

    def _wait_busy_pulse(self) -> None:
        """Wait for the busy pulse that follows a command, then for ready."""
        conn = self._require_open()
        start = time.monotonic()
        while conn.dsr:
            if time.monotonic() - start > self.BUSY_DETECT_TIME:
                return  # command finished before we saw it busy
            time.sleep(0.001)
        self._wait_ready()

    def _raw_write(self, text: str, wait_done: bool = True) -> None:
        conn = self._require_open()
        self._wait_ready()
        conn.write(f"{text}\r\n".encode("ascii"))
        conn.flush()
        if wait_done:
            self._wait_busy_pulse()

    def write(self, command: str) -> None:
        with self._lock:
            self._raw_write(command)

    def query(self, command: str, timeout: float | None = None) -> str:
        """Send a query and return the answer line.

        ``timeout`` defaults to the read timeout of the connection (``set_timeout``).
        Raises ``TimeoutError`` if no complete line arrives in time and
        ``ReadCancelled`` if ``cancel()`` was called while waiting.
        """
        with self._lock:
            conn = self._require_open()
            # The answer arrives on its own; no busy wait for queries.
            self._raw_write(command, wait_done=False)
            line = self._read_line(conn.timeout if timeout is None else timeout)
            response = line.decode("ascii", errors="replace").strip()
            if not response:
                raise TimeoutError(tr("No response from {port} to {command}",
                                  port=self.port, command=command))
            return response

    # Waiting for an answer is split into short slices so that cancel() takes
    # effect within this time, also during a long measurement (100 NPLC, slow
    # AC filter, external trigger).
    CANCEL_POLL = 0.2

    def _read_line(self, timeout: float | None) -> bytes:
        conn = self._require_open()
        deadline = time.monotonic() + (timeout if timeout is not None else 1e9)
        previous = conn.timeout
        buffer = bytearray()
        try:
            while not buffer.endswith(b"\n"):
                if self._cancel.is_set():
                    raise ReadCancelled(f"{self.port}: read cancelled")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                conn.timeout = min(self.CANCEL_POLL, remaining)
                buffer += conn.read_until(b"\n")
        finally:
            conn.timeout = previous
        if buffer and not buffer.endswith(b"\n"):
            # A cut-off answer must never be taken as a reading.
            raise TimeoutError(f"{self.port}: incomplete answer {bytes(buffer)!r}")
        return bytes(buffer)

    def cancel(self) -> None:
        """Abort waiting for an answer (thread-safe). Stays in effect until ``clear_cancel()``.

        The instrument itself keeps measuring; ``device_clear()`` aborts that.
        """
        self._cancel.set()

    def clear_cancel(self) -> None:
        self._cancel.clear()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def set_timeout(self, seconds: float) -> None:
        self._require_open().timeout = seconds

    # -- helpers ------------------------------------------------------------
    def identify(self) -> str:
        identification = self.query("*IDN?")
        fields = identification.split(",")
        if len(fields) < 2 or fields[1].strip().upper() != "34401A":
            raise InstrumentError(tr("Unexpected instrument: {idn}", idn=identification))
        return identification

    def calibration_message(self) -> str:
        return decode_scpi_string(self.query("CAL:STR?"))

    def calibration_count(self) -> int:
        return int(float(self.query("CAL:COUN?")))

    def calibration_secured(self) -> bool:
        state = self.query("CAL:SEC:STAT?").strip().lstrip("+")
        if state not in ("0", "1"):
            raise InstrumentError(f"Unexpected calibration security state: {state!r}")
        return state == "1"

    def terminals(self) -> str:
        """Return 'FRON' or 'REAR' (the switch itself cannot be set remotely)."""
        return self.query("ROUT:TERM?").strip()

    def read_errors(self, limit: int = 25) -> list[str]:
        """Empty the error queue; return all entries other than +0."""
        errors = []
        for _ in range(limit):
            response = self.query("SYST:ERR?")
            if response.split(",", 1)[0].strip().lstrip("+") == "0":
                return errors
            errors.append(response)
        errors.append("Error queue did not empty")
        return errors

    def check_errors(self, context: str) -> None:
        errors = self.read_errors()
        if errors:
            raise InstrumentError(f"{context}: " + "; ".join(errors))

    def device_clear(self) -> None:
        """RS-232 equivalent of a device clear: abort a measurement in progress."""
        conn = self._require_open()
        conn.write(b"\x03")  # sent regardless of DSR: the meter may be busy
        conn.flush()
        time.sleep(0.2)
        self.discard_pending_output()


@dataclass
class DeviceInfo:
    """Everything known about one detected instrument."""

    port: str
    identification: str = ""
    calibration_message: str | None = None
    calibration_count: int | None = None
    firmware: str = ""
    terminals: str = ""
    usb_serial: str = ""
    port_description: str = ""
    location: str = ""
    errors: list[str] = field(default_factory=list)
    simulated: bool = False

    @property
    def label(self) -> str:
        """Unique, human-readable name: the stored ID, else the port."""
        message = (self.calibration_message or "").strip()
        return message if message else self.port

    @property
    def manufacturer(self) -> str:
        return self.identification.split(",")[0].strip() if self.identification else ""


def candidate_ports(include_all: bool = False):
    """Serial ports worth probing. Legacy ttyS ports without hardware are skipped."""
    ports = []
    for info in sorted(list_ports.comports(), key=lambda p: p.device):
        if not include_all and (info.hwid in ("n/a", "", None)):
            continue
        ports.append(info)
    return ports


def probe_port(port_info) -> DeviceInfo | None:
    """Return DeviceInfo if an HP 34401A answers on this port, otherwise None."""
    meter = HP34401A(port_info.device)
    try:
        identification = meter.connect()
    except SERIAL_ERRORS:
        meter.close(local=False)
        return None
    info = DeviceInfo(
        port=port_info.device,
        identification=identification,
        usb_serial=getattr(port_info, "serial_number", "") or "",
        port_description=getattr(port_info, "description", "") or "",
        location=getattr(port_info, "location", "") or "",
    )
    try:
        info.calibration_message = meter.calibration_message()
        info.calibration_count = meter.calibration_count()
        info.firmware = meter.query("SYST:VERS?")
        info.terminals = meter.terminals()
    except SERIAL_ERRORS as error:
        info.errors.append(str(error))
    finally:
        meter.close()
    return info


def discover(include_all_ports: bool = False, simulate: bool = False) -> list[DeviceInfo]:
    """Probe all candidate ports in parallel and return the instruments found."""
    if simulate:
        from .simulator import simulated_devices
        return simulated_devices()
    ports = candidate_ports(include_all_ports)
    if not ports:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(ports))) as pool:
        results = list(pool.map(probe_port, ports))
    return [r for r in results if r is not None]


def open_instrument(info: DeviceInfo) -> HP34401A:
    """Create a (real or simulated) driver object for a detected device."""
    if info.simulated:
        from .simulator import SimulatedHP34401A
        return SimulatedHP34401A(info.port, info.calibration_message or "")
    return HP34401A(info.port)
