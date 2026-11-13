"""Settings form for one instrument (function, range, resolution, math, trigger, evaluation)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from ..analysis import MIN_READINGS
from ..functions import (AC_FILTERS, AC_RESOLUTIONS, AUTO, AUTOZERO_CHOICES, CONFIDENCE_LEVELS,
                         CONV_LINEAR, CONV_NONE, CONV_PER_LENGTH, CONVERSION_LABELS,
                         DBM_REFERENCES, DC_RESOLUTIONS, FUNCTION_GROUPS, FUNCTIONS, GATE_TIMES,
                         IMPEDANCE_CHOICES, MATH_DB, MATH_DBM, MATH_LABELS, MATH_LIMIT, MATH_NONE,
                         MATH_NULL, TRIGGER_SOURCES, DeviceConfig, active_range,
                         configuration_commands, digits_text, estimated_reading_time,
                         format_reading, format_value, preview_value, resolution_step, validate)
from ..specs import SPEC_PERIODS, instrument_error
from ..i18n import localize_number, tr
from .widgets import Card, DataCombo, FormRow, hint, muted



def _spin(minimum=-1.2e9, maximum=1.2e9, decimals=6, suffix="") -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSuffix(suffix)
    box.setKeyboardTracking(False)
    box.setButtonSymbols(QDoubleSpinBox.NoButtons)
    box.setProperty("plain", True)  # see style.py: keeps the text field visible
    return box


def _pair(*rows) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    for row in rows:
        layout.addWidget(row)
    return widget


class DeviceSettingsPanel(QScrollArea):
    """Editable DeviceConfig. Emits ``changed`` on every edit."""

    changed = Signal()
    apply_mode_requested = Signal()

    def __init__(self, config: DeviceConfig, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._loading = False
        self._last_value: float | None = None
        self._loop_mode = False
        inner = QWidget()
        self.setWidget(inner)
        root = QVBoxLayout(inner)
        root.setContentsMargins(4, 4, 8, 4)
        root.setSpacing(12)

        # --- function ---------------------------------------------------
        card = Card(tr("Measurement function"))
        self.function = DataCombo()
        self.function.set_grouped_items(
            [(tr(heading), [(k, tr(FUNCTIONS[k].label)) for k in keys])
             for heading, keys in FUNCTION_GROUPS])
        self.function_hint = hint("")
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText(tr("optional, e.g. \"Red 1\" – appears in the export"))
        self.row_label = FormRow(tr("Label of the measured object"), self.label_edit)
        self.loop_label_hint = muted(tr("In a measurement series the label comes from the object "
                                        "list under Measurement."))
        card.body.addWidget(FormRow(tr("What should be measured?"), self.function))
        card.body.addWidget(self.function_hint)
        card.body.addWidget(self.row_label)
        card.body.addWidget(self.loop_label_hint)
        root.addWidget(card)
        self._root = root

        # --- range / resolution ------------------------------------------
        card = Card(tr("Range & resolution"))
        self.range = DataCombo()
        self.resolution = DataCombo()
        self.autozero = DataCombo()
        self.autozero.set_items([(k, tr(v)) for k, v in AUTOZERO_CHOICES])
        self.impedance = DataCombo()
        self.impedance.set_items([(k, tr(v)) for k, v in IMPEDANCE_CHOICES])
        self.ac_filter = DataCombo()
        self.ac_filter.set_items([(k, tr(v)) for k, v in AC_FILTERS])
        self.row_range = FormRow(tr("Range"), self.range)
        self.row_resolution = FormRow(tr("Resolution (digits)"), self.resolution)
        self.preview = QLabel()
        self.preview.setObjectName("Callout")
        self.preview.setWordWrap(True)
        self.row_autozero = FormRow(tr("Autozero"), self.autozero)
        self.row_impedance = FormRow(tr("Input resistance"), self.impedance)
        self.row_filter = FormRow(tr("AC filter (lowest signal frequency)"), self.ac_filter)
        for widget in (self.row_range, self.row_resolution, self.preview, self.row_autozero,
                       self.row_impedance, self.row_filter):
            card.body.addWidget(widget)
        self.speed_label = muted("")
        card.body.addWidget(self.speed_label)
        root.addWidget(card)

        # --- instrument math -------------------------------------------------
        card = Card(tr("Math function (in the instrument)"),
                    tr("Calculated inside the multimeter; the instrument returns the result."))
        self.card_math = card
        self.math = DataCombo()
        card.body.addWidget(FormRow(tr("Function"), self.math))
        self.null_auto = QCheckBox(tr("First reading becomes the null value"))
        self.null_value = _spin()
        self.row_null = QWidget()
        lay = QVBoxLayout(self.row_null)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.null_auto)
        lay.addWidget(FormRow(tr("Null value (offset)"), self.null_value))
        self.dbm_ref = DataCombo()
        self.dbm_ref.set_items([(r, f"{r} Ω") for r in DBM_REFERENCES])
        self.row_dbm = FormRow(tr("dBm reference resistance"), self.dbm_ref)
        self.db_auto = QCheckBox(tr("First reading becomes the dB reference"))
        self.db_value = _spin(-200, 200, 3, " dBm")
        self.row_db = QWidget()
        lay = QVBoxLayout(self.row_db)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.db_auto)
        lay.addWidget(FormRow(tr("dB reference"), self.db_value))
        self.limit_low = _spin()
        self.limit_high = _spin()
        self.row_limits = _pair(FormRow(tr("Lower limit"), self.limit_low),
                                FormRow(tr("Upper limit"), self.limit_high))
        for row in (self.row_null, self.row_dbm, self.row_db, self.row_limits):
            card.body.addWidget(row)
        root.addWidget(card)

        # --- PC evaluation ---------------------------------------------------
        card = Card(tr("Evaluation (on the PC)"),
                    tr("Measurement result (mean and scatter, optionally with uncertainty) for "
                       "every series, and an optional conversion of each reading. The original "
                       "readings are kept."))
        self.card_evaluation = card
        self.conversion = DataCombo()
        self.conversion.set_items([(k, tr(v)) for k, v in CONVERSION_LABELS.items()])
        card.body.addWidget(FormRow(tr("Conversion"), self.conversion))
        self.conv_factor = _spin(-1e12, 1e12, 9)
        self.conv_offset = _spin(-1e12, 1e12, 9)
        self.conv_unit = QLineEdit()
        self.conv_unit.setMaxLength(12)
        self.conv_unit.setPlaceholderText(tr("e.g. bar"))
        self.row_linear = QWidget()
        lay = QVBoxLayout(self.row_linear)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(_pair(FormRow(tr("Factor"), self.conv_factor),
                            FormRow(tr("Offset"), self.conv_offset)))
        lay.addWidget(FormRow(tr("Unit of the result"), self.conv_unit))
        lay.addWidget(muted(tr("Example 4–20 mA → 0–10 bar: factor 625, offset −2.5, unit bar.")))
        self.conv_length = _spin(0.000001, 1e6, 4, " m")
        self.row_length = FormRow(tr("Cable length"), self.conv_length)
        card.body.addWidget(self.row_linear)
        card.body.addWidget(self.row_length)

        self.uncertainty = QCheckBox(tr("Calculate measurement uncertainty"))
        self.uncertainty.setToolTip(tr("Off: only mean, standard deviation, minimum and maximum "
                                       "are calculated."))
        card.body.addWidget(self.uncertainty)
        self.uncertainty_box = QWidget()
        box = QVBoxLayout(self.uncertainty_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(8)
        self.confidence = DataCombo()
        self.confidence.set_items([(level, tr(text)) for level, text in CONFIDENCE_LEVELS])
        box.addWidget(FormRow(tr("Confidence level of the uncertainty"), self.confidence))
        self.spec_period = DataCombo()
        self.spec_period.set_items([(key, tr(text)) for key, text in SPEC_PERIODS])
        self.spec_period.setToolTip(tr("Accuracy columns of the data sheet (user's guide, "
                                       "chapter 8): the longer since calibration, the larger "
                                       "the permitted error. Normal case: 1 year."))
        box.addWidget(FormRow(tr("Instrument accuracy (time since calibration)"),
                              self.spec_period))
        self.signal_frequency = _spin(3, 300e3, 1, " Hz")
        self.row_signal_frequency = FormRow(tr("Signal frequency (for the AC accuracy)"),
                                            self.signal_frequency)
        box.addWidget(self.row_signal_frequency)
        self.error_preview = hint("")
        self.error_preview.setTextFormat(Qt.RichText)
        box.addWidget(self.error_preview)
        box.addWidget(muted(tr(
            "Result x̄ ± u with u = t · s/√n + h: Student factor t, standard deviation s, "
            "number of readings n and the instrument error h from the data sheet. At least "
            "{n} readings are needed for a valid result.", n=MIN_READINGS)))
        card.body.addWidget(self.uncertainty_box)
        root.addWidget(card)

        # --- trigger ---------------------------------------------------------
        card = Card(tr("Trigger & averaging"),
                    tr("Trigger = what starts a measurement. Averaging = how many individual "
                       "readings the instrument takes per stored point."))
        self.card_trigger = card
        self.trigger = DataCombo()
        self.trigger.set_items([(k, tr(v)) for k, v in TRIGGER_SOURCES])
        self.trigger_hint = muted("")
        self.delay_auto = QCheckBox(tr("Automatic trigger delay (recommended)"))
        self.delay = _spin(0, 3600, 4, " s")
        self.samples = QSpinBox()
        self.samples.setRange(1, 1000)
        card.body.addWidget(FormRow(tr("Trigger source"), self.trigger))
        card.body.addWidget(self.trigger_hint)
        card.body.addWidget(self.delay_auto)
        self.row_delay = FormRow(tr("Delay (settling time before each reading)"),
                                 self.delay)
        card.body.addWidget(self.row_delay)
        card.body.addWidget(FormRow(tr("Readings per point (averaged)"), self.samples))
        card.body.addWidget(muted(tr("Example: 10 → the instrument measures 10 times in a row and "
                                     "the mean is stored. Less noise, takes 10 times as long.")))
        root.addWidget(card)

        # --- instrument ---------------------------------------------------------
        card = Card(tr("Instrument"))
        self.display_on = QCheckBox(tr("Display on during the measurement"))
        self.beeper_on = QCheckBox(tr("Beeper (limit test, min/max, diode test)"))
        self.beeper_on.setToolTip(tr("The continuity tone cannot be switched off (manual, "
                                     "\"Beeper Control\")."))
        card.body.addWidget(self.display_on)
        card.body.addWidget(self.beeper_on)
        root.addWidget(card)

        # --- mode only --------------------------------------------------------
        card = Card(tr("Without data logging"))
        self.card_mode = card
        self.mode_callout = QLabel()
        self.mode_callout.setObjectName("Callout")
        self.mode_callout.setWordWrap(True)
        self.apply_button = QPushButton(tr("Switch instrument to this mode"))
        self.apply_button.setToolTip(tr("Configures the instrument and returns it to the front "
                                        "panel."))
        self.apply_button.clicked.connect(self.apply_mode_requested)
        card.body.addWidget(self.mode_callout)
        card.body.addWidget(self.apply_button)
        self.scpi_preview = muted("")
        self.scpi_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card.body.addWidget(self.scpi_preview)
        root.addWidget(card)
        root.addStretch(1)

        self.set_config(config)
        self._connect_signals()

    # ------------------------------------------------------------------------
    def _connect_signals(self):
        self.function.currentIndexChanged.connect(self._function_changed)
        for combo in (self.math, self.range, self.resolution, self.autozero, self.impedance,
                      self.ac_filter, self.dbm_ref, self.trigger, self.conversion,
                      self.confidence, self.spec_period):
            combo.currentIndexChanged.connect(self._edited)
        for box in (self.null_auto, self.db_auto, self.delay_auto, self.display_on,
                    self.beeper_on, self.uncertainty):
            box.toggled.connect(self._edited)
        for spin in (self.null_value, self.db_value, self.limit_low, self.limit_high,
                     self.delay, self.conv_factor, self.conv_offset, self.conv_length,
                     self.signal_frequency):
            spin.valueChanged.connect(self._edited)
        self.samples.valueChanged.connect(self._edited)
        self.label_edit.textChanged.connect(self._edited)
        self.conv_unit.textChanged.connect(self._edited)

    def _function_changed(self):
        if self._loading:
            return
        config = self.config()
        config.range = AUTO
        if config.math not in config.func.math:
            config.math = MATH_NONE
        self._last_value = None
        self.set_config(config)
        self.changed.emit()

    def _edited(self):
        if self._loading:
            return
        self._update_visibility()
        self.changed.emit()

    # ------------------------------------------------------------------------
    def set_config(self, config: DeviceConfig):
        self._loading = True
        try:
            func = config.func
            self.function.select_data(config.function)
            self.function_hint.setText(tr(func.hint) if func.hint else "")
            self.function_hint.setVisible(bool(func.hint))
            self.label_edit.setText(config.label)

            self.range.set_items([(AUTO, tr("Automatic (autorange)"))] + [
                (value, label) for label, value in func.ranges], config.range)
            if func.kind == "dc":
                self.resolution.set_items([(row[0], "") for row in DC_RESOLUTIONS],
                                          config.dc_resolution)
                self.row_resolution.label.setText(tr("Resolution (digits) / integration time"))
            elif func.kind == "ac":
                self.resolution.set_items([(row[0], "") for row in AC_RESOLUTIONS],
                                          config.ac_resolution)
                self.row_resolution.label.setText(tr("Resolution (digits)"))
            elif func.kind == "freq":
                self.resolution.set_items([(g, "") for g, _, _ in GATE_TIMES], config.gate_time)
                self.row_resolution.label.setText(tr("Gate time / resolution"))
            else:
                self.resolution.clear()
            self.row_range.label.setText(tr("Input voltage range")
                                         if func.range_is_input_voltage else tr("Range"))
            self.autozero.select_data(config.autozero)
            self.impedance.select_data(config.high_impedance)
            self.ac_filter.select_data(config.ac_filter)

            allowed = [m for m in MATH_LABELS if m in func.math] or [MATH_NONE]
            self.math.set_items([(m, tr(MATH_LABELS[m])) for m in allowed], config.math)
            self.null_auto.setChecked(config.null_offset is None)
            self.null_value.setValue(config.null_offset or 0.0)
            self.dbm_ref.select_data(config.dbm_reference)
            self.db_auto.setChecked(config.db_reference is None)
            self.db_value.setValue(config.db_reference or 0.0)
            self.limit_low.setValue(config.limit_lower)
            self.limit_high.setValue(config.limit_upper)

            self.conversion.select_data(config.conversion)
            self.conv_factor.setValue(config.conv_factor)
            self.conv_offset.setValue(config.conv_offset)
            self.conv_unit.setText(config.conv_unit)
            self.conv_length.setValue(config.conv_length)
            self.uncertainty.setChecked(config.uncertainty)
            self.confidence.select_data(config.confidence)
            self.spec_period.select_data(config.spec_period)
            self.signal_frequency.setValue(config.signal_frequency)

            self.trigger.select_data(config.trigger_source)
            self.delay_auto.setChecked(config.trigger_delay is None)
            self.delay.setValue(config.trigger_delay or 0.0)
            self.samples.setValue(config.samples)
            self.display_on.setChecked(config.display_on)
            self.beeper_on.setChecked(config.beeper_on)
        finally:
            self._loading = False
        self._update_visibility()

    def config(self) -> DeviceConfig:
        function = self.function.currentData() or "VOLT:DC"
        func = FUNCTIONS[function]
        config = DeviceConfig(function=function)
        config.label = self.label_edit.text().strip()
        if func.kind != "fixed":
            data = self.range.currentData()
            config.range = data if data is not None else AUTO
        data = self.resolution.currentData()
        if func.kind == "dc" and data is not None:
            config.dc_resolution = data
        elif func.kind == "ac" and data is not None:
            config.ac_resolution = data
        elif func.kind == "freq" and data is not None:
            config.gate_time = data
        config.autozero = self.autozero.currentData()
        config.high_impedance = bool(self.impedance.currentData())
        config.ac_filter = self.ac_filter.currentData()
        config.math = self.math.currentData() or MATH_NONE
        config.null_offset = None if self.null_auto.isChecked() else self.null_value.value()
        config.dbm_reference = self.dbm_ref.currentData()
        config.db_reference = None if self.db_auto.isChecked() else self.db_value.value()
        config.limit_lower = self.limit_low.value()
        config.limit_upper = self.limit_high.value()
        config.conversion = self.conversion.currentData() or CONV_NONE
        config.conv_factor = self.conv_factor.value()
        config.conv_offset = self.conv_offset.value()
        config.conv_unit = self.conv_unit.text().strip()
        config.conv_length = self.conv_length.value()
        config.uncertainty = self.uncertainty.isChecked()
        config.confidence = self.confidence.currentData() or config.confidence
        config.spec_period = self.spec_period.currentData() or config.spec_period
        config.signal_frequency = self.signal_frequency.value()
        config.trigger_source = self.trigger.currentData()
        config.trigger_delay = None if self.delay_auto.isChecked() else self.delay.value()
        config.samples = self.samples.value()
        config.display_on = self.display_on.isChecked()
        config.beeper_on = self.beeper_on.isChecked()
        return config

    # ------------------------------------------------------------------------
    def set_last_value(self, value: float | None):
        """Use a real reading for the resolution preview."""
        self._last_value = value
        config = self.config()
        self._update_resolution_texts(config)
        self._update_error_preview(config)

    def set_loop_mode(self, enabled: bool):
        self._loop_mode = enabled
        self._update_visibility()

    def _update_resolution_texts(self, config: DeviceConfig):
        func = config.func
        if func.kind == "fixed":
            self.preview.setText(tr("Display: {value} (fixed range, 5½ digits)",
                                    value=format_reading(config, func.example)))
            return
        example = preview_value(config, self._last_value)
        for index in range(self.resolution.count()):
            key = self.resolution.itemData(index)
            variant = DeviceConfig.from_dict(config.to_dict())
            if func.kind == "dc":
                variant.dc_resolution = key
                _, speed, nplc, digits = next(r for r in DC_RESOLUTIONS if r[0] == key)
                text = (f"{digits_text(digits)} · {tr(speed)} "
                        f"({localize_number(f'{nplc:g}')} NPLC)")
            elif func.kind == "ac":
                variant.ac_resolution = key
                text = digits_text(variant.digits)
            else:
                variant.gate_time = key
                gate = next(lbl for g, lbl, _ in GATE_TIMES if g == key)
                text = f"{tr('Gate time')} {gate} · {digits_text(variant.digits)}"
            self.resolution.setItemText(index, f"{text}   →   {format_reading(variant, example)}")

        step = resolution_step(config, example)
        rng = active_range(config, example)
        source = tr("last reading") if self._last_value is not None else tr("example value")
        lines = [tr("A reading will look like this: <b>{value}</b> ({source})",
                    value=format_reading(config, example), source=source)]
        if step is not None and rng is not None:
            lines.append(tr("Smallest step {step} in the {range} range",
                            step=format_value(step, config.unit, significant=1),
                            range=format_value(rng, config.unit, significant=1)))
        lines.append(tr("More digits or NPLC = finer resolution and less noise, but slower."))
        self.preview.setText("<br>".join(lines))

    def _update_visibility(self):
        config = self.config()
        func = config.func
        fixed = func.kind == "fixed"
        # Continuity / diode test are front-panel modes: only what matters for switching the
        # instrument is shown, and "Switch instrument to this mode" moves up.
        self.card_math.setVisible(self.math.count() > 1)
        self.card_evaluation.setVisible(not fixed)
        self.card_trigger.setVisible(not fixed)
        self.speed_label.setVisible(not fixed)
        self.display_on.setVisible(not fixed)
        position = 1 if fixed else self._root.count() - 2  # before the stretch
        if self._root.indexOf(self.card_mode) != position:
            self._root.removeWidget(self.card_mode)
            self._root.insertWidget(position, self.card_mode)
        self.row_range.setVisible(not fixed)
        self.row_resolution.setVisible(not fixed)
        self.row_autozero.setVisible(func.autozero)
        self.row_impedance.setVisible(func.impedance)
        self.row_filter.setVisible(func.ac_filter)
        self.row_label.setVisible(not self._loop_mode and not fixed)
        self.loop_label_hint.setVisible(self._loop_mode and not fixed)
        math = config.math
        self.row_null.setVisible(math == MATH_NULL)
        self.null_value.setEnabled(not self.null_auto.isChecked())
        self.row_dbm.setVisible(math in (MATH_DB, MATH_DBM))
        self.row_db.setVisible(math == MATH_DB)
        self.db_value.setEnabled(not self.db_auto.isChecked())
        self.row_limits.setVisible(math == MATH_LIMIT)
        self.row_delay.setEnabled(not self.delay_auto.isChecked())
        unit = config.func.unit
        for spin in (self.null_value, self.limit_low, self.limit_high):
            spin.setSuffix(f" {unit}" if unit else "")

        self.row_linear.setVisible(config.conversion == CONV_LINEAR)
        self.row_length.setVisible(config.conversion == CONV_PER_LENGTH)
        self.uncertainty_box.setVisible(config.uncertainty)
        self.row_signal_frequency.setVisible(func.kind == "ac")
        self._update_error_preview(config)

        self.trigger_hint.setText({
            "IMM": tr("The tool triggers each reading at the selected interval (normal case)."),
            "EXT": tr("Each reading waits for a pulse on the Ext Trig jack (rear panel), e.g. "
                      "from a test fixture."),
            "BUS": tr("The tool sends a software trigger (*TRG) for each reading. Behaves like "
                      "internal, useful for testing."),
        }[config.trigger_source])

        self._update_resolution_texts(config)
        seconds = estimated_reading_time(config)
        rate = tr("under 0.2 s") if seconds < 0.2 else "≈ " + localize_number(f"{seconds:.1f}") + " s"
        self.speed_label.setText(tr("Estimated time per point: {rate}", rate=rate))

        if fixed:
            self.mode_callout.setText(tr(
                "<b>{function}</b> is used directly on the instrument: it decides by its own "
                "threshold and beeps. The button below switches the instrument to this mode and "
                "returns it to the front panel. It is not logged in the measurement plan; in the "
                "live mode the readings can be watched on the PC.",
                function=tr(func.label)))
        else:
            self.mode_callout.setText(tr(
                "Configure the instrument with these settings and return it to the front panel "
                "without logging readings."))
        problems = validate(config)
        if problems:
            self.scpi_preview.setText("⚠ " + " ".join(problems))
        else:
            self.scpi_preview.setText("SCPI: " + " · ".join(configuration_commands(config)))

    def _update_error_preview(self, config: DeviceConfig):
        """Instrument error h for the last (or an example) reading, from the data sheet."""
        value = preview_value(config, self._last_value)
        error = instrument_error(config, value)
        if error is None:
            self.error_preview.setText(tr("Instrument error h: not specified by the data sheet "
                                          "for these settings."))
            return
        text = tr("Instrument error h at <b>{value}</b>: ± <b>{h}</b>",
                  value=format_reading(config, value),
                  h=format_value(error.value, config.unit, significant=2))
        if error.range is not None:
            text += " " + tr("({range} range)",
                             range=format_value(error.range, config.unit, significant=1))
        self.error_preview.setText("<br>".join([text] + [tr(note) for note in error.notes]))

    def set_busy(self, busy: bool):
        self.widget().setEnabled(not busy)
