"""Application icon, drawn at runtime (no image files needed)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def render_icon(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 64.0
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor("#2dd4bf"))
    gradient.setColorAt(1, QColor("#0f766e"))
    p.setBrush(gradient)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(2 * s, 2 * s, 60 * s, 60 * s), 14 * s, 14 * s)
    # display window
    p.setBrush(QColor("#0b1f1d"))
    p.drawRoundedRect(QRectF(10 * s, 12 * s, 44 * s, 26 * s), 5 * s, 5 * s)
    # waveform
    path = QPainterPath()
    for i in range(0, 41):
        x = 13 * s + i * (38 * s / 40)
        y = 25 * s - math.sin(i / 40 * 2 * math.pi * 1.5) * 7 * s
        path.moveTo(QPointF(x, y)) if i == 0 else path.lineTo(QPointF(x, y))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#5eead4"), 2.6 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)
    # input jacks
    p.setPen(Qt.NoPen)
    for i, color in enumerate(("#f8fafc", "#f8fafc", "#ef4444")):
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF((20 + i * 12) * s, 49 * s), 4 * s, 4 * s)
    p.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(render_icon(size))
    return icon
