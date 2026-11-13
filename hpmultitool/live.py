"""Live mode: keep instruments connected, read continuously, change settings on the fly.

Each instrument gets a ``LiveDevice`` thread with its own serial connection.
The GUI sends commands (new configuration, pause, read rate) through a queue;
the thread applies them between two readings and reports readings and state
changes through a shared event queue - the same ``Event`` objects as a normal
measurement session, so the GUI can reuse its handling.
"""

from __future__ import annotations

import queue
import threading
import time

from .acquisition import Event, apply_configuration, read_point
from .functions import DeviceConfig, configuration_commands, read_timeout
from .i18n import tr
from .instrument import SERIAL_ERRORS, DeviceInfo, open_instrument

MAX_ERRORS_IN_ROW = 5


class LiveDevice(threading.Thread):
    """Continuous readings from one instrument until ``stop()``."""

    def __init__(self, slot: int, info: DeviceInfo, config: DeviceConfig,
                 events: queue.Queue, interval: float = 0.0):
        super().__init__(name=f"HP34401A-live-{info.port}", daemon=True)
        self.slot = slot
        self.info = info
        self.config = config
        self.events = events
        self.interval = interval
        self._commands: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._paused = False
        self.t0 = time.monotonic()

    # -- called from the GUI thread ------------------------------------------
    def set_config(self, config: DeviceConfig) -> None:
        self._commands.put(("config", DeviceConfig.from_dict(config.to_dict())))

    def set_interval(self, seconds: float) -> None:
        self._commands.put(("interval", float(seconds)))

    def set_paused(self, paused: bool) -> None:
        self._commands.put(("pause", bool(paused)))

    def stop(self) -> None:
        self._stop_event.set()
        self._commands.put(("wake", None))

    # -- thread ----------------------------------------------------------------
    def emit(self, kind, text="", **kwargs):
        self.events.put(Event(kind, self.slot, text, **kwargs))

    def run(self):
        meter = open_instrument(self.info)
        try:
            self.emit("status", tr("Connecting …"))
            meter.connect()
            apply_configuration(meter, self.info, self.config)
            meter.set_timeout(read_timeout(self.config))
            self.emit("configured", tr("live"), data={"config": self.config})
            self._loop(meter)
        except SERIAL_ERRORS as error:
            self.emit("error", str(error))
        except Exception as error:  # never let a thread die silently
            self.emit("error", f"{type(error).__name__}: {error}")
        finally:
            meter.close(local=True)
            self.emit("finished", tr("Local"))

    def _loop(self, meter):
        point = 0
        errors_in_row = 0
        next_read = time.monotonic()
        while not self._stop_event.is_set():
            # Apply all pending commands, then wait until the next reading is due.
            timeout = 0.2 if self._paused else max(0.0, next_read - time.monotonic())
            try:
                command, value = self._commands.get(timeout=timeout)
            except queue.Empty:
                command = None
            if command is not None:
                self._apply_command(meter, command, value)
                continue  # look for further commands first
            if self._paused or self._stop_event.is_set():
                continue
            started = time.monotonic()
            reading = read_point(meter, self.config, self.slot, point, self.t0)
            if self._stop_event.is_set() and reading.status == "TIMEOUT":
                break
            self.emit("reading", reading=reading)
            point += 1
            if reading.status in ("TIMEOUT", "ERROR"):
                errors_in_row += 1
                if errors_in_row >= MAX_ERRORS_IN_ROW:
                    self.emit("error", tr("{n} measurement errors in a row – live mode stopped.",
                                          n=MAX_ERRORS_IN_ROW))
                    break
            else:
                errors_in_row = 0
            next_read = started + self.interval

    def _apply_command(self, meter, command, value):
        if command == "config":
            try:
                meter.write("*CLS")
                for scpi in configuration_commands(value):
                    meter.write(scpi)
                meter.check_errors(tr("Instrument rejected the configuration"))
            except (ValueError, *SERIAL_ERRORS) as error:
                self.emit("warning", str(error))
                # restore the previous, known-good configuration
                try:
                    apply_configuration(meter, self.info, self.config)
                except SERIAL_ERRORS:
                    pass
                self.emit("configured", tr("live"), data={"config": self.config})
                return
            self.config = value
            meter.set_timeout(read_timeout(value))
            self.emit("configured", tr("live"), data={"config": value})
        elif command == "interval":
            self.interval = value
        elif command == "pause":
            self._paused = value
            self.emit("paused" if value else "resumed")


class LiveSession:
    """All live devices together; the GUI polls ``events``."""

    def __init__(self, devices: list[tuple[DeviceInfo, DeviceConfig]], interval: float = 0.0):
        labels = [info.label for info, _ in devices]
        if not devices:
            raise ValueError(tr("No instrument selected."))
        if len(set(labels)) != len(labels):
            raise ValueError(tr("Two selected instruments have the same ID. Please assign unique "
                                "IDs in the advanced settings."))
        self.events: queue.Queue[Event] = queue.Queue()
        self.devices = [LiveDevice(slot, info, config, self.events, interval)
                        for slot, (info, config) in enumerate(devices)]
        self.t0 = time.monotonic()
        for device in self.devices:
            device.t0 = self.t0

    def start(self):
        for device in self.devices:
            device.start()

    def stop(self):
        for device in self.devices:
            device.stop()

    def set_interval(self, seconds: float):
        for device in self.devices:
            device.set_interval(seconds)

    @property
    def running(self) -> bool:
        return any(device.is_alive() for device in self.devices)
