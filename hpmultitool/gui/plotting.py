"""Plot helpers shared by the measurement and the live view."""

from __future__ import annotations

import time
from datetime import datetime

import pyqtgraph as pg


class ClockAxis(pg.AxisItem):
    """Time axis showing the time of day as HH:MM:SS (x values are Unix timestamps)."""

    STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600,
             43200, 86400]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enableAutoSIPrefix(False)  # timestamps must not be shown as "x1e+09"

    def tickSpacing(self, minVal, maxVal, size):  # noqa: N802 - Qt naming
        span = max(maxVal - minVal, 1e-9)
        wanted = max(2, int(size / 90))  # roughly one label per 90 px
        major = next((step for step in self.STEPS if span / step <= wanted), self.STEPS[-1])
        minor = next((step for step in reversed(self.STEPS) if step < major), major)
        return [(major, 0), (minor, 0)]

    def tickValues(self, minVal, maxVal, size):  # noqa: N802
        # Align ticks to local clock time, not to UTC.
        offset = -time.localtime(minVal if minVal > 0 else time.time()).tm_gmtoff
        levels = []
        for spacing, _ in self.tickSpacing(minVal, maxVal, size):
            start = (minVal - offset) // spacing * spacing + offset
            values = []
            value = start
            while value <= maxVal and len(values) < 200:
                if value >= minVal:
                    values.append(value)
                value += spacing
            levels.append((spacing, values))
        return levels

    def tickStrings(self, values, scale, spacing):  # noqa: N802
        return [datetime.fromtimestamp(v).strftime("%H:%M:%S") if v > 0 else "" for v in values]
