"""Right-hand area of the measurement page: series banner, readout tiles, chart, table,
overview and log."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QPlainTextEdit,
                               QTableView, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from ..acquisition import Reading
from ..export import (SUMMARY_ALWAYS, SUMMARY_HEADERS, MeasurementRecord, summary_columns,
                      summary_rows)
from ..i18n import tr
from .loop_banner import LoopBanner
from .plotting import ClockAxis, add_limit_lines, apply_plot_theme, style_plot
from .readings import WARN_COLOR, ReadingsModel, ReadoutTile
from .widgets import hint, section_label

# Overview table: columns n … maximum are numbers; the note column is highlighted.
SUMMARY_NUMERIC = range(3, SUMMARY_ALWAYS + 2)
SUMMARY_NOTE = len(SUMMARY_HEADERS) - 1
MAX_SYMBOL_POINTS = 500


class ResultsView(QWidget):
    def __init__(self, theme: str):
        super().__init__()
        self.theme = theme
        self.tiles: list[ReadoutTile] = []
        self.curves = []
        self.plot_data: list[tuple[list, list]] = []
        self._plot_dirty = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(section_label(tr("Live readings")))
        self.banner = LoopBanner()
        layout.addWidget(self.banner)

        self.tiles_layout = QHBoxLayout()
        self.tiles_layout.setSpacing(10)
        self.tiles_placeholder = hint(tr("Start a measurement to see live values."))
        self.tiles_layout.addWidget(self.tiles_placeholder)
        layout.addLayout(self.tiles_layout)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.GraphicsLayoutWidget()
        self.tabs.addTab(self.plot_widget, tr("Chart"))
        self.table_model = ReadingsModel()
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.tabs.addTab(self.table, tr("Table"))
        self.summary_table = QTableWidget(0, len(SUMMARY_HEADERS))
        self.summary_table.setHorizontalHeaderLabels([tr(h) for h in SUMMARY_HEADERS])
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.summary_table, tr("Overview"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.tabs.addTab(self.log, tr("Log"))
        layout.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------ general
    def apply_theme(self, theme: str):
        self.theme = theme
        apply_plot_theme(self.plot_widget, theme)

    def append_log(self, line: str):
        self.log.appendPlainText(line)

    @property
    def has_chart(self) -> bool:
        return bool(self.curves)

    def clear_results(self):
        self.table_model.reset()
        self.summary_table.setRowCount(0)

    def show_overview(self):
        self.tabs.setCurrentWidget(self.summary_table)

    # ------------------------------------------------------------------ one step
    def prepare_step(self, assignments, colors: list[str]):
        """New tiles and one plot per instrument for the next measurement step."""
        while self.tiles_layout.count():
            item = self.tiles_layout.takeAt(0)
            if item.widget() is not None and item.widget() is not self.tiles_placeholder:
                item.widget().deleteLater()
        self.tiles_placeholder.setVisible(False)
        self.tiles = []
        for (info, config), color in zip(assignments, colors):
            tile = ReadoutTile(info, config, color)
            tile.set_status(tr("connecting …"))
            self.tiles.append(tile)
            self.tiles_layout.addWidget(tile, 1)

        self.plot_widget.clear()
        self.curves, self.plot_data = [], []
        first = None
        for slot, ((info, config), color) in enumerate(zip(assignments, colors)):
            item = self.plot_widget.addPlot(row=slot, col=0,
                                            axisItems={"bottom": ClockAxis(orientation="bottom")})
            style_plot(item, self.theme)
            unit = config.unit
            title = f"{info.label} · {config.label}" if config.label else info.label
            if unit in ("dB", "dBm", ""):
                item.setLabel("left", f"{title} ({unit})" if unit else title)
            else:
                item.setLabel("left", title, units=unit)
            item.setLabel("bottom", tr("Time of day"))
            item.setClipToView(True)
            item.setDownsampling(auto=True, mode="peak")
            add_limit_lines(item, config, self.theme)
            curve = item.plot([], [], pen=pg.mkPen(color, width=2), symbol="o", symbolSize=4,
                              symbolBrush=color, symbolPen=None)
            if first is None:
                first = item
            else:
                item.setXLink(first)
            self.curves.append(curve)
            self.plot_data.append(([], []))

    def tile(self, slot: int) -> ReadoutTile | None:
        return self.tiles[slot] if 0 <= slot < len(self.tiles) else None

    def set_tile_status(self, text: str):
        for tile in self.tiles:
            tile.set_status(text)

    def add_point(self, slot: int, reading: Reading):
        xs, ys = self.plot_data[slot]
        xs.append(reading.timestamp.timestamp())
        ys.append(reading.value)
        self._plot_dirty = True

    def add_rows(self, rows):
        self.table_model.add(rows)
        if rows and self.tabs.currentWidget() is self.table:
            self.table.scrollToBottom()

    def refresh_plot(self, force: bool = False):
        if not (self._plot_dirty or force):
            return
        self._plot_dirty = False
        for curve, (xs, ys) in zip(self.curves, self.plot_data):
            curve.setData(xs, ys)
            curve.setSymbol("o" if len(xs) <= MAX_SYMBOL_POINTS else None)

    # ------------------------------------------------------------------ tables
    def show_record(self, record: MeasurementRecord):
        """Replace table and overview with a finished record (e.g. from live mode)."""
        self.table_model.reset(record.rows())
        self.update_summary(record)

    def remove_step(self, step: int):
        self.table_model.remove_step(step)

    def update_summary(self, record: MeasurementRecord | None):
        if record is None:
            return
        rows = summary_rows(record)
        self.summary_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                item = QTableWidgetItem(text)
                if c in SUMMARY_NUMERIC:
                    item.setTextAlignment(int(Qt.AlignRight | Qt.AlignVCenter))
                if c == SUMMARY_NOTE and text:
                    item.setForeground(QColor(WARN_COLOR))
                self.summary_table.setItem(r, c, item)
        # Optional columns (uncertainty, calculated result, stability, notes) only when used.
        keep = set(summary_columns(rows))
        for column in range(len(SUMMARY_HEADERS)):
            self.summary_table.setColumnHidden(column, column not in keep)
