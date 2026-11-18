"""Measurement series (loop): several objects measured one after another.

GUI-independent: how the objects are distributed over the instruments and
where a running series stands.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .functions import DeviceConfig
from .i18n import N_, tr
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


def parse_objects(text: str) -> list[str]:
    """Object names from a text with one object per line (empty lines are ignored)."""
    return [line.strip() for line in text.splitlines() if line.strip()]


@dataclass
class LoopTemplate:
    name: str             # shown to the user (translated for built-in templates)
    objects: list[str]
    builtin: str = ""     # source text of the built-in name; empty for own templates


@dataclass
class TemplateStore:
    """Built-in and own object templates for the measurement series.

    Own templates are stored as plain text (name and objects). A built-in template
    is never changed: an own template with the same name replaces it (deleting that
    one brings the built-in back), deleting a built-in template hides it, and
    ``restore`` shows all hidden built-in templates again.
    """

    custom: list[tuple[str, list[str]]] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data) -> "TemplateStore":
        store = cls()
        if not isinstance(data, dict):
            return store
        for entry in data.get("custom", []):
            try:
                name, objects = entry
            except (TypeError, ValueError):
                continue
            if isinstance(name, str) and isinstance(objects, list) and name.strip():
                store.custom.append((name.strip(), [str(o) for o in objects]))
        store.hidden = [h for h in data.get("hidden", []) if isinstance(h, str)]
        return store

    def to_dict(self) -> dict:
        return {"custom": [[name, list(objects)] for name, objects in self.custom],
                "hidden": list(self.hidden)}

    def templates(self) -> list[LoopTemplate]:
        own = {name.casefold() for name, _ in self.custom}
        result = [LoopTemplate(tr(name), [o.strip() for o in tr(items).split(",")], name)
                  for name, items in LOOP_TEMPLATES
                  if name not in self.hidden and tr(name).casefold() not in own]
        result += [LoopTemplate(name, list(objects)) for name, objects in self.custom]
        return result

    def find(self, name: str) -> LoopTemplate | None:
        key = name.strip().casefold()
        for template in self.templates():
            if template.name.casefold() == key:
                return template
        return None

    def save(self, name: str, objects: list[str]) -> None:
        """Add an own template or replace the one with the same name."""
        name = name.strip()
        if not name:
            raise ValueError("empty template name")
        key = name.casefold()
        self.custom = [(n, o) for n, o in self.custom if n.casefold() != key]
        self.custom.append((name, list(objects)))

    def delete(self, name: str) -> None:
        template = self.find(name)
        if template is None:
            return
        if template.builtin:
            if template.builtin not in self.hidden:
                self.hidden.append(template.builtin)
        else:
            key = template.name.casefold()
            self.custom = [(n, o) for n, o in self.custom if n.casefold() != key]

    def restore(self) -> None:
        """Show the built-in templates again (own templates are kept)."""
        self.hidden = []


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


def build_loop_steps(devices: Assignment, objects: dict[str, list[str]]) -> list[Assignment]:
    """Each instrument works through its own object list (``objects`` by instrument ID).

    Step n measures the n-th object of every instrument whose list is that long; an
    instrument with a shorter list rests in the last steps, one without objects is not
    measured at all.
    """
    lists = [(info, config, objects.get(info.label, [])) for info, config in devices]
    steps = []
    for index in range(max((len(names) for _, _, names in lists), default=0)):
        step = []
        for info, config, names in lists:
            if index < len(names):
                per_object = DeviceConfig.from_dict(config.to_dict())
                per_object.label = names[index]
                step.append((info, per_object))
        steps.append(step)
    return steps


def object_lists_from(data) -> dict[str, list[str]]:
    """Stored object lists by instrument ID; ``""`` is the list for instruments without one.

    Accepts the former single shared list as well (it becomes the default list).
    """
    if isinstance(data, list):
        data = {"": data}
    if not isinstance(data, dict):
        return {}
    return {str(key): [str(name).strip() for name in names if str(name).strip()]
            for key, names in data.items() if isinstance(names, list)}
