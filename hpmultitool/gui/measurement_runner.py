"""Runs a measurement (one step or a whole series) and feeds the results into the views.

The window validates the input and builds the steps; the runner owns the
running ``Session``, the record and the autosave writer, polls the event queue
on a timer and drives the series banner (connect, measure, repeat, skip).
"""

from __future__ import annotations

import queue
import time
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from .. import APP_NAME
from ..acquisition import Plan, Session
from ..export import DeviceRecord, LiveCsvWriter, MeasurementRecord
from ..functions import configuration_commands, format_reading
from ..i18n import localize_number, tr
from ..series import ADVANCE_AUTO, Assignment, LoopState
from .plan_card import PlanCard
from .results_view import ResultsView
from .time_input import hms

POLL_MS, PLOT_MS, COUNTDOWN_MS = 100, 300, 200
MAX_EVENTS_PER_POLL = 2000


class MeasurementRunner(QObject):
    running_changed = Signal(bool)
    message = Signal(str, str)           # text, level (info / warn / error)
    value_received = Signal(object, float)  # DeviceInfo, reading value

    def __init__(self, plan_card: PlanCard, results: ResultsView, color_of, parent=None):
        super().__init__(parent)
        self.plan_card = plan_card
        self.results = results
        self.color_of = color_of
        self.session: Session | None = None
        self.loop: LoopState | None = None
        self.plan: Plan | None = None
        self.record: MeasurementRecord | None = None
        self.writer: LiveCsvWriter | None = None
        self.slot_records: list[DeviceRecord] = []
        self._errors: list[str] = []
        self._start_time: float | None = None

        self.poll_timer = self._timer(POLL_MS, self._poll)
        self.plot_timer = self._timer(PLOT_MS, self.results.refresh_plot)
        self.countdown_timer = self._timer(COUNTDOWN_MS, self._countdown_tick)
        banner = results.banner
        banner.measure_requested.connect(self.measure_now)
        banner.repeat_requested.connect(self.repeat_step)
        banner.skip_requested.connect(self.skip_step)
        banner.end_requested.connect(self.end_series)

    def _timer(self, interval, slot) -> QTimer:
        timer = QTimer(self)
        timer.setInterval(interval)
        timer.timeout.connect(slot)
        return timer

    def _log(self, text: str, level: str = "info"):
        self.message.emit(text, level)

    @property
    def busy(self) -> bool:
        return self.session is not None or self.loop is not None

    # ------------------------------------------------------------------ start / stop
    def start(self, steps: list[Assignment], plan: Plan, record: MeasurementRecord,
              writer: LiveCsvWriter | None, loop: LoopState | None):
        self.plan = plan
        self.record = record
        self.writer = writer
        self._errors = []
        self.results.clear_results()
        self.running_changed.emit(True)
        if loop is not None:
            self.loop = loop
            self._log(tr("Series with {n} steps started.", n=loop.total))
            self._prompt()
        else:
            self._run_step(steps[0], 1)

    def _run_step(self, assignments: Assignment, step: int):
        plan = self.plan
        session = Session(assignments, plan)
        self.slot_records = [DeviceRecord(info, config, step=step,
                                          stability_used=plan.stability is not None)
                             for info, config in assignments]
        self.record.devices.extend(self.slot_records)
        self.results.prepare_step(assignments, [self.color_of(info) for info, _ in assignments])
        self.plan_card.reset_progress()
        self.session = session
        for info, config in assignments:
            self._log(f"{info.label}: " + " · ".join(configuration_commands(config)))
        self._log(tr("Preparing measurement …"))
        self._start_time = None
        session.start()
        self.poll_timer.start()
        self.plot_timer.start()
        self.plan_card.set_stop_enabled(True)

    def stop(self):
        """Stop button: end the running step, or the series while it waits for the user."""
        if self.session is not None:
            self.session.stop()
            self.plan_card.set_stop_enabled(False)
            self._log(tr("Stop requested – finishing the current reading …"))
        elif self.loop is not None:
            self.end_series()

    def shutdown(self, timeout: float = 15.0):
        """Stop everything when the window closes; waits for the instruments to be released."""
        if self.loop is not None:
            self.loop.ending = True
        if self.session is not None:
            self.session.stop()
            deadline = time.monotonic() + timeout
            while self.session is not None and self.session.running \
                    and time.monotonic() < deadline:
                QApplication.processEvents()
                time.sleep(0.05)
            self._poll()
        if self.writer is not None:
            self.writer.close()

    # ------------------------------------------------------------------ events
    def _poll(self):
        session = self.session
        if session is None:
            return
        new_rows = []
        for _ in range(MAX_EVENTS_PER_POLL):
            try:
                event = session.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event, new_rows)
        self.results.add_rows(new_rows)
        self._update_progress()
        if not session.running and session.events.empty():
            self._step_finished()

    def _handle_event(self, event, new_rows):
        slot = event.slot
        if event.kind == "started":
            self._start_time = time.monotonic()
            if self.record.started_at is None:
                self.record.started_at = self.session.started_at
            self._log(tr("Measurement running."))
            self.results.set_tile_status(tr("measuring"))
            return
        rec = self.slot_records[slot] if slot >= 0 else None
        name = rec.info.label if rec else ""
        tile = self.results.tile(slot)
        if event.kind == "reading":
            self._handle_reading(slot, rec, event.reading, new_rows)
        elif event.kind in ("status", "ready"):
            if event.data.get("instrument_minmax"):
                rec.instrument_minmax = event.data["instrument_minmax"]
            if tile and self._start_time is None:
                tile.set_status(event.text)
        elif event.kind == "warning":
            self._log(f"{name}: {event.text}", "warn")
        elif event.kind == "error":
            self._errors.append(f"{name}: {event.text}")
            self._log(f"{name}: {event.text}", "error")
            if tile:
                tile.set_status(tr("Error"))
        elif event.kind == "stable":
            rec.stable_value = event.data["value"]
            rec.stable_after = event.data["after"]
            if tile:
                tile.set_status(tr("stable ✓"))
            self._log(tr("{device}: stable after {s} s – final value {value}",
                         device=name, s=localize_number(f"{rec.stable_after:.1f}"),
                         value=format_reading(rec.config, rec.stable_value)))
        elif event.kind == "unstable":
            if tile:
                tile.set_status(tr("⚠ not stable"))
            self._log(tr("{device}: did not become stable within the maximum duration.",
                         device=name), "warn")
        elif event.kind == "finished":
            if tile and rec.stable_value is None and not rec.stability_used:
                tile.set_status(event.text)

    def _handle_reading(self, slot, rec: DeviceRecord, reading, new_rows):
        rec.readings.append(reading)
        if self.writer is not None:
            try:
                self.writer.add(rec, reading)
            except OSError as error:
                self._log(tr("Autosave error: {error}", error=error), "warn")
                self.writer = None
        new_rows.append((rec, reading))
        if reading.value is not None:
            self.results.add_point(slot, reading)
            self.value_received.emit(rec.info, reading.value)
        self.results.tile(slot).show_reading(reading, rec.stats())
        if reading.status in ("TIMEOUT", "ERROR"):
            self._log(tr("{device}: measurement error ({status}) at point {point}",
                         device=rec.info.label, status=reading.status, point=reading.point),
                      "warn")

    def _update_progress(self):
        if self._start_time is None:
            return
        elapsed = time.monotonic() - self._start_time
        duration = self.record.duration
        count = sum(len(rec.readings) for rec in self.slot_records)
        if duration:
            self.plan_card.set_progress(elapsed / duration)
            text = f"{hms(elapsed)} / {hms(duration)}"
        else:
            if duration is None:
                self.plan_card.set_progress(None)
            text = hms(elapsed)
        prefix = ""
        if self.loop is not None:
            prefix = tr("Step {i}/{n}", i=self.loop.index + 1, n=self.loop.total) + "  ·  "
        self.plan_card.set_progress_text(prefix + tr("{time}  ·  {n} readings", time=text, n=count))

    # ------------------------------------------------------------------ end of a step
    def _step_finished(self):
        self.poll_timer.stop()
        self.plot_timer.stop()
        self.results.refresh_plot(force=True)
        self.session = None
        self.plan_card.reset_progress(full=self.record.duration is not None)
        self.results.update_summary(self.record)
        loop = self.loop
        if loop is not None and not loop.ending:
            loop.index += 1
            if loop.index < loop.total:
                self._show_errors()
                self._prompt()
                return
        self._finish_all()

    def _show_errors(self):
        if self._errors:
            QMessageBox.warning(self.parent(), APP_NAME, tr("The measurement reported errors:")
                                + "\n\n" + "\n".join(self._errors))
            self._errors = []

    def _finish_all(self):
        self.loop = None
        self.results.banner.setVisible(False)
        self.countdown_timer.stop()
        self.record.finished_at = datetime.now().astimezone()
        if self.writer is not None:
            self.writer.close()
            self._log(tr("Autosave: {path}", path=self.writer.path))
            self.writer = None
        count = sum(len(rec.readings) for rec in self.record.devices)
        self._log(tr("Measurement finished – {n} readings. Export as .csv or .txt now.", n=count))
        self.running_changed.emit(False)
        if self.record.loop or len(self.record.devices) > 1:
            self.results.show_overview()
        self._show_errors()

    # ------------------------------------------------------------------ series control
    def _prompt(self):
        loop = self.loop
        self.results.banner.show_prompt(loop.index, loop.total, loop.steps[loop.index],
                                        can_repeat=loop.index > 0)
        self.plan_card.set_stop_enabled(True)
        if loop.advance == ADVANCE_AUTO and loop.index > 0:
            loop.countdown_end = time.monotonic() + loop.pause
            self.countdown_timer.start()
            self._countdown_tick()
        else:
            loop.countdown_end = None
            QApplication.beep()

    def _cancel_countdown(self):
        self.loop.countdown_end = None
        self.countdown_timer.stop()

    def _countdown_tick(self):
        loop = self.loop
        if loop is None or loop.countdown_end is None:
            self.countdown_timer.stop()
            return
        remaining = loop.countdown_end - time.monotonic()
        if remaining <= 0:
            self.countdown_timer.stop()
            self.measure_now()
            return
        self.results.banner.show_countdown(int(remaining) + 1)

    def measure_now(self):
        loop = self.loop
        if loop is None or self.session is not None:
            return
        self._cancel_countdown()
        self.results.banner.show_measuring(loop.index, loop.total)
        self._run_step(loop.steps[loop.index], loop.index + 1)

    def repeat_step(self):
        loop = self.loop
        if loop is None or self.session is not None or loop.index == 0:
            return
        self._cancel_countdown()
        loop.index -= 1
        step = loop.index + 1
        self.record.devices = [rec for rec in self.record.devices if rec.step != step]
        self.results.remove_step(step)
        self.results.update_summary(self.record)
        self._log(tr("Repeating step {i}.", i=step))
        self._prompt()

    def skip_step(self):
        loop = self.loop
        if loop is None or self.session is not None:
            return
        self._cancel_countdown()
        names = ", ".join(config.label for _, config in loop.steps[loop.index])
        self._log(tr("Step {i} skipped ({names}).", i=loop.index + 1, names=names), "warn")
        loop.index += 1
        if loop.index < loop.total:
            self._prompt()
        else:
            self._finish_all()

    def end_series(self):
        if self.loop is None:
            return
        self.loop.ending = True
        self._log(tr("Series finished."))
        if self.session is not None:
            self.session.stop()  # _step_finished completes the series
            return
        self._finish_all()
