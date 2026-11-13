"""Plot helpers shared by the measurement and the live view."""

from __future__ import annotations

import time
from datetime import datetime

import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from ..functions import (CONV_NONE, MATH_LIMIT, TOL_ABSOLUTE, TOL_PERCENT, TOL_RANGE,
                         DeviceConfig)
from .style import THEMES


def style_plot(item, theme: str) -> None:
    """Apply the theme colours to the axes and grid of one plot."""
    colors = THEMES[theme]
    for axis in ("left", "bottom"):
        ax = item.getAxis(axis)
        ax.setPen(pg.mkPen(colors["grid"]))
        ax.setTextPen(pg.mkPen(colors["muted"]))
    item.showGrid(x=True, y=True, alpha=0.25)


def plot_items(widget: pg.GraphicsLayoutWidget) -> list:
    """All plots stacked in the first column of a layout widget."""
    layout = widget.ci
    return [layout.getItem(r, 0) for r in range(layout.layout.rowCount())
            if layout.getItem(r, 0) is not None]


def apply_plot_theme(widget: pg.GraphicsLayoutWidget, theme: str) -> None:
    widget.setBackground(THEMES[theme]["plot_bg"])
    for item in plot_items(widget):
        style_plot(item, theme)


def limit_values(config: DeviceConfig) -> list[float]:
    """Limits to draw in the plot, when they refer to the measured value."""
    if config.math == MATH_LIMIT:
        return [config.limit_lower, config.limit_upper]
    if config.conversion != CONV_NONE:
        return []
    if config.tolerance == TOL_PERCENT:
        d = abs(config.tol_nominal) * config.tol_value / 100
        return [config.tol_nominal - d, config.tol_nominal + d]
    if config.tolerance == TOL_ABSOLUTE:
        return [config.tol_nominal - config.tol_value, config.tol_nominal + config.tol_value]
    if config.tolerance == TOL_RANGE:
        return [config.tol_low, config.tol_high]
    return []


def add_limit_lines(item, config: DeviceConfig, theme: str) -> None:
    for value in limit_values(config):
        item.addLine(y=value, pen=pg.mkPen(THEMES[theme]["danger"], width=1, style=Qt.DotLine))


def render_png(widget: pg.GraphicsLayoutWidget, path: str, theme: str, ratio: float = 2.0) -> bool:
    """Save the visible chart as PNG, rendered at ``ratio`` times the screen resolution."""
    image = QImage(int(widget.width() * ratio), int(widget.height() * ratio),
                   QImage.Format_ARGB32)
    image.fill(QColor(THEMES[theme]["plot_bg"]))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    widget.scene().render(painter, QRectF(image.rect()),
                          widget.mapToScene(widget.viewport().rect()).boundingRect())
    painter.end()
    return image.save(path, "PNG")


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
