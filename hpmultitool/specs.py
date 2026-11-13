"""Accuracy specifications of the HP 34401A (User's Guide, chapter 8, pages 216-220).

``instrument_error`` returns the maximum error h of one reading according to
the data sheet: ±(% of reading + % of range) for the selected calibration
interval, plus the additional errors from the footnotes that the settings
determine (resolution/NPLC, 2-wire ohms without null, autozero off, AC filter
and signal level, low frequencies). The specifications apply at 23 °C ± 5 °C
(24 h: ± 1 °C) after one hour of warm-up; temperature coefficients outside this
range are not included.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .functions import AUTO, MATH_DB, MATH_DBM, MATH_NULL, DeviceConfig
from .i18n import N_

PERIOD_24H, PERIOD_90D, PERIOD_1Y = "24h", "90d", "1y"
SPEC_PERIODS = [
    (PERIOD_24H, N_("24 hours after calibration (23 °C ± 1 °C)")),
    (PERIOD_90D, N_("90 days after calibration (23 °C ± 5 °C)")),
    (PERIOD_1Y, N_("1 year after calibration (23 °C ± 5 °C)")),
]
SPEC_PERIOD_DEFAULT = PERIOD_1Y
_COLUMN = {PERIOD_24H: 0, PERIOD_90D: 1, PERIOD_1Y: 2}

# --------------------------------------------------------------- DC (page 216)
# range -> ((% reading, % range) for 24 h, 90 days, 1 year)
_DC_VOLTS = {
    0.1: ((0.0030, 0.0030), (0.0040, 0.0035), (0.0050, 0.0035)),
    1: ((0.0020, 0.0006), (0.0030, 0.0007), (0.0040, 0.0007)),
    10: ((0.0015, 0.0004), (0.0020, 0.0005), (0.0035, 0.0005)),
    100: ((0.0020, 0.0006), (0.0035, 0.0006), (0.0045, 0.0006)),
    1000: ((0.0020, 0.0006), (0.0035, 0.0010), (0.0045, 0.0010)),
}
# Resistance: 4-wire, or 2-wire with math null (footnote 4).
_RESISTANCE = {
    100: ((0.0030, 0.0030), (0.008, 0.004), (0.010, 0.004)),
    1e3: ((0.0020, 0.0005), (0.008, 0.001), (0.010, 0.001)),
    1e4: ((0.0020, 0.0005), (0.008, 0.001), (0.010, 0.001)),
    1e5: ((0.0020, 0.0005), (0.008, 0.001), (0.010, 0.001)),
    1e6: ((0.002, 0.001), (0.008, 0.001), (0.010, 0.001)),
    1e7: ((0.015, 0.001), (0.020, 0.001), (0.040, 0.001)),
    1e8: ((0.300, 0.010), (0.800, 0.010), (0.800, 0.010)),
}
_DC_CURRENT = {
    0.01: ((0.005, 0.010), (0.030, 0.020), (0.050, 0.020)),
    0.1: ((0.01, 0.004), (0.030, 0.005), (0.050, 0.005)),
    1: ((0.05, 0.006), (0.080, 0.010), (0.100, 0.010)),
    3: ((0.10, 0.020), (0.120, 0.020), (0.120, 0.020)),
}
# Continuity (1 kΩ range) and diode test (1 V range).
_FIXED = {
    "CONT": (1000.0, ((0.002, 0.010), (0.008, 0.020), (0.010, 0.020))),
    "DIOD": (1.0, ((0.002, 0.010), (0.008, 0.020), (0.010, 0.020))),
}
_DC_TABLES = {"VOLT:DC": _DC_VOLTS, "RES": _RESISTANCE, "FRES": _RESISTANCE,
              "CURR:DC": _DC_CURRENT}

# Additional noise error for less than 6½ digits, % of range (page 217, "Operating
# Characteristics"); with [10]: plus 20 µV (DCV), 4 µA (DCI) or 20 mΩ (resistance).
_NOISE = {100: (0.0, False), 10: (0.0, False), 1: (0.001, False), 0.2: (0.001, True),
          0.02: (0.01, True)}
_NOISE_EXTRA = {"VOLT:DC": 20e-6, "CURR:DC": 4e-6, "RES": 20e-3, "FRES": 20e-3}
TWO_WIRE_LEAD_ERROR = 0.2       # Ω, 2-wire ohms without math null (footnote 4)

# --------------------------------------------------------------- AC (page 218)
# (low Hz, high Hz, ((% reading, % range) 24 h, 90 days, 1 year))
_ACV_100MV = [
    (3, 5, ((1.00, 0.03), (1.00, 0.04), (1.00, 0.04))),
    (5, 10, ((0.35, 0.03), (0.35, 0.04), (0.35, 0.04))),
    (10, 20e3, ((0.04, 0.03), (0.05, 0.04), (0.06, 0.04))),
    (20e3, 50e3, ((0.10, 0.05), (0.11, 0.05), (0.12, 0.05))),
    (50e3, 100e3, ((0.55, 0.08), (0.60, 0.08), (0.60, 0.08))),
    (100e3, 300e3, ((4.00, 0.50), (4.00, 0.50), (4.00, 0.50))),
]
_ACV_1V_UP = [
    (3, 5, ((1.00, 0.02), (1.00, 0.03), (1.00, 0.03))),
    (5, 10, ((0.35, 0.02), (0.35, 0.03), (0.35, 0.03))),
    (10, 20e3, ((0.04, 0.02), (0.05, 0.03), (0.06, 0.03))),
    (20e3, 50e3, ((0.10, 0.04), (0.11, 0.05), (0.12, 0.05))),
    (50e3, 100e3, ((0.55, 0.08), (0.60, 0.08), (0.60, 0.08))),
    (100e3, 300e3, ((4.00, 0.50), (4.00, 0.50), (4.00, 0.50))),
]
_ACI_1A = [
    (3, 5, ((1.00, 0.04),) * 3),
    (5, 10, ((0.30, 0.04),) * 3),
    (10, 5e3, ((0.10, 0.04),) * 3),
]
_ACI_3A = [
    (3, 5, ((1.10, 0.06),) * 3),
    (5, 10, ((0.35, 0.06),) * 3),
    (10, 5e3, ((0.15, 0.06),) * 3),
]
# Additional low-frequency error, % of reading, by AC filter (3 / 20 / 200 Hz);
# None = not specified (filter too fast for this frequency).
_AC_LOW_FREQ = [
    (10, 20, {3: 0.0, 20: 0.74, 200: None}),
    (20, 40, {3: 0.0, 20: 0.22, 200: None}),
    (40, 100, {3: 0.0, 20: 0.06, 200: 0.73}),
    (100, 200, {3: 0.0, 20: 0.01, 200: 0.22}),
    (200, 1e3, {3: 0.0, 20: 0.0, 200: 0.18}),
]

# ---------------------------------------------------- frequency/period (page 220)
_FREQ = [
    (3, 5, (0.10, 0.10, 0.10)),
    (5, 10, (0.05, 0.05, 0.05)),
    (10, 40, (0.03, 0.03, 0.03)),
    (40, 300e3, (0.006, 0.01, 0.01)),
]
# Additional low-frequency error, % of reading, by resolution (gate time).
_FREQ_LOW = [
    (3, 5, {6: 0.0, 5: 0.12, 4: 0.12}),
    (5, 10, {6: 0.0, 5: 0.17, 4: 0.17}),
    (10, 40, {6: 0.0, 5: 0.2, 4: 0.2}),
    (40, 100, {6: 0.0, 5: 0.06, 4: 0.21}),
    (100, 300, {6: 0.0, 5: 0.03, 4: 0.21}),
    (300, 1e3, {6: 0.0, 5: 0.01, 4: 0.07}),
    (1e3, float("inf"), {6: 0.0, 5: 0.0, 4: 0.02}),
]


@dataclass
class InstrumentError:
    """Maximum error h of one reading and how it was obtained."""

    value: float                          # h, in the unit of the reading
    range: float | None = None            # range the specification refers to
    notes: list[str] = field(default_factory=list)   # source texts for tr()


def assumed_range(ranges: list[float], value: float) -> float:
    """Range used with autorange: the smallest one that holds the value (≤ 100 %).

    Conservative: between 100 % and 120 % the instrument may still be on the
    lower range, which would give a smaller error.
    """
    magnitude = abs(value)
    for candidate in sorted(ranges):
        if magnitude <= candidate:
            return candidate
    return max(ranges)


def _band(table, frequency):
    for low, high, entry in table:
        if low <= frequency < high or (frequency == high == table[-1][1]):
            return entry
    return None


def instrument_error(config: DeviceConfig, value: float,
                     period: str | None = None) -> InstrumentError | None:
    """Maximum error h of the reading ``value``; None if the data sheet does not cover it."""
    period = period or config.spec_period
    column = _COLUMN.get(period, _COLUMN[SPEC_PERIOD_DEFAULT])
    func = config.func
    if config.math in (MATH_DB, MATH_DBM) or func.key == "VOLT:DC:RAT":
        return None  # dB values and ratios: input and reference errors not separable
    notes: list[str] = []
    if config.math == MATH_NULL:
        notes.append(N_("Null active: h refers to the displayed (relative) value."))

    if func.key in _FIXED:
        rng, rows = _FIXED[func.key]
        pct_reading, pct_range = rows[column]
        return InstrumentError((pct_reading * abs(value) + pct_range * rng) / 100, rng, notes)

    if func.key in _DC_TABLES:
        table = _DC_TABLES[func.key]
        rng = config.range if config.range != AUTO else assumed_range(list(table), value)
        if config.range == AUTO:
            notes.append(N_("Autorange: smallest range holding the value assumed."))
        pct_reading, pct_range = table[rng][column]
        h = (pct_reading * abs(value) + pct_range * rng) / 100
        noise, extra = _NOISE.get(config.nplc, (0.0, False))
        h += noise * rng / 100 + (_NOISE_EXTRA[func.key] if extra else 0.0)
        if noise or extra:
            notes.append(N_("Includes the noise error for less than 6½ digits."))
        if func.key == "RES" and config.math != MATH_NULL:
            h += TWO_WIRE_LEAD_ERROR
            notes.append(N_("2-wire without null: +0.2 Ω lead resistance."))
        if func.autozero and config.autozero != "ON":
            h += 0.0002 * rng / 100 + (5e-6 if func.key == "VOLT:DC" else 0.0)
            notes.append(N_("Autozero off: +0.0002 % of range."))
        return InstrumentError(h, rng, notes)

    if func.kind == "ac":
        frequency = config.signal_frequency
        if func.key == "VOLT:AC":
            ranges = [r for _, r in func.ranges]
            rng = config.range if config.range != AUTO else assumed_range(ranges, value)
            bands = _ACV_100MV if rng == 0.1 else _ACV_1V_UP
        else:
            rng = config.range if config.range != AUTO else assumed_range([1, 3], value)
            bands = _ACI_1A if rng == 1 else _ACI_3A
        if config.range == AUTO:
            notes.append(N_("Autorange: smallest range holding the value assumed."))
        entry = _band(bands, frequency)
        if entry is None:
            return None  # frequency outside the specified bands
        if frequency < 10 and config.ac_filter != 3:
            return None  # below 10 Hz only the slow filter is specified
        pct_reading, pct_range = entry[column]
        low = _band(_AC_LOW_FREQ, frequency)
        if low is not None:
            extra = low.get(config.ac_filter)
            if extra is None:
                return None  # AC filter too fast for this frequency
            pct_reading += extra
            if extra:
                notes.append(N_("Includes the low-frequency error of the AC filter."))
        share = abs(value) / rng
        if share < 0.05:  # footnote 4: specified for inputs > 5 % of range
            pct_range += 0.13 if frequency >= 50e3 else 0.1
            notes.append(N_("Input below 5 % of range: additional error included."))
            if share < 0.01:
                notes.append(N_("Input below 1 % of range: not specified by the data sheet."))
        return InstrumentError((pct_reading * abs(value) + pct_range * rng) / 100, rng, notes)

    if func.kind == "freq":
        if value == 0:
            return None
        frequency = abs(value) if func.key == "FREQ" else 1 / abs(value)
        entry = _band(_FREQ, frequency)
        if entry is None:
            return None
        pct = entry[column] + _band(_FREQ_LOW, frequency)[config.digits]
        return InstrumentError(pct * abs(value) / 100, None, notes)
    return None
