"""Measurement series (loop): several objects measured one after another.

GUI-independent: how the objects are distributed over the instruments and
where a running series stands.
"""

from __future__ import annotations

from dataclasses import dataclass

from .functions import DeviceConfig
from .i18n import N_
from .instrument import DeviceInfo

MODE_SINGLE, MODE_LOOP = "single", "loop"
ADVANCE_CONFIRM, ADVANCE_AUTO = "confirm", "auto"

LOOP_TEMPLATES = [
    (N_("Sensor cable, 6 cores"), N_("red, yellow, black, white, green, brown")),
    (N_("4 cores (DIN 47100)"), N_("white, brown, green, yellow")),
    (N_("Core colours IEC 60757 (10)"),
     N_("black, brown, red, orange, yellow, green, blue, violet, grey, white")),
    (N_("Numbered 1 … 8"), "1, 2, 3, 4, 5, 6, 7, 8"),
]

Assignment = list[tuple[DeviceInfo, DeviceConfig]]


@dataclass
class LoopState:
    """Progress of a measurement series (loop) over several objects."""

    steps: list[Assignment]
    advance: str
    pause: float
    index: int = 0
    countdown_end: float | None = None
    ending: bool = False

    @property
    def total(self) -> int:
        return len(self.steps)


def build_loop_steps(devices: Assignment, objects: list[str]) -> list[Assignment]:
    """Distribute objects over the selected devices: n devices measure n objects per step."""
    steps = []
    count = len(devices)
    for start in range(0, len(objects), count):
        chunk = objects[start:start + count]
        step = []
        for (info, config), name in zip(devices, chunk):
            per_object = DeviceConfig.from_dict(config.to_dict())
            per_object.label = name
            step.append((info, per_object))
        steps.append(step)
    return steps


def step_count(objects: int, devices: int) -> int:
    """Number of steps needed for ``objects`` objects with ``devices`` instruments."""
    return -(-objects // max(1, devices)) if objects else 0
