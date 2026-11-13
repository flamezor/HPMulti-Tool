"""Measurement functions of the HP 34401A and SCPI command generation.

Everything here follows chapters 3 and 4 of the HP 34401A User's Guide:
ranges, resolution/NPLC choices, AC filters, gate times, input resistance,
autozero, math operations (with the function compatibility table on
page 124) and triggering.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from .i18n import N_, localize_number, tr

AUTO = "AUTO"

# ---------------------------------------------------------------- ranges
DCV_RANGES = [("100 mV", 0.1), ("1 V", 1), ("10 V", 10), ("100 V", 100), ("1000 V", 1000)]
ACV_RANGES = [("100 mV", 0.1), ("1 V", 1), ("10 V", 10), ("100 V", 100), ("750 V", 750)]
DCI_RANGES = [("10 mA", 0.01), ("100 mA", 0.1), ("1 A", 1), ("3 A", 3)]
ACI_RANGES = [("1 A", 1), ("3 A", 3)]
OHM_RANGES = [("100 Ω", 100), ("1 kΩ", 1e3), ("10 kΩ", 1e4), ("100 kΩ", 1e5),
              ("1 MΩ", 1e6), ("10 MΩ", 1e7), ("100 MΩ", 1e8)]

# ------------------------------------------------- resolution (DC functions)
# Front-panel DIGITS choices and their integration time (manual p. 54).
# key, speed text, nplc, digits (4/5/6 = 4½/5½/6½)
DC_RESOLUTIONS = [
    ("4F", N_("fast"), 0.02, 4),
    ("4S", N_("slow"), 1, 4),
    ("5F", N_("fast"), 0.2, 5),
    ("5S", N_("slow"), 10, 5),
    ("6F", N_("fast"), 10, 6),
    ("6S", N_("slow"), 100, 6),
]
DC_RESOLUTION_DEFAULT = "6F"

# AC voltage/current: digits only change the reported resolution.
AC_RESOLUTIONS = [("4", "", 4), ("5", "", 5), ("6", "", 6)]
AC_RESOLUTION_DEFAULT = "6"

AC_FILTERS = [
    (3, N_("Slow · from 3 Hz (≈7 s settling time)")),
    (20, N_("Medium · from 20 Hz (default)")),
    (200, N_("Fast · from 200 Hz")),
]
AC_FILTER_DEFAULT = 20

# Frequency/period: the gate time sets the resolution (manual p. 57, 220).
GATE_TIMES = [(0.01, "10 ms", 4), (0.1, "100 ms", 5), (1.0, "1 s", 6)]
GATE_DEFAULT = 0.1

AUTOZERO_CHOICES = [("ON", N_("On (default)")), ("OFF", N_("Off (faster)")),
                    ("ONCE", N_("Once"))]

IMPEDANCE_CHOICES = [
    (False, N_("10 MΩ (all ranges, default)")),
    (True, N_(">10 GΩ (ranges 100 mV … 10 V)")),
]

# --------------------------------------------------------------------- math
MATH_NONE, MATH_NULL, MATH_MINMAX, MATH_DB, MATH_DBM, MATH_LIMIT = (
    "NONE", "NULL", "AVER", "DB", "DBM", "LIM")
MATH_LABELS = {
    MATH_NONE: N_("None"),
    MATH_NULL: N_("Null (relative measurement)"),
    MATH_MINMAX: N_("Min / max / average"),
    MATH_DB: N_("dB (relative)"),
    MATH_DBM: N_("dBm"),
    MATH_LIMIT: N_("Limit test"),
}
DBM_REFERENCES = [50, 75, 93, 110, 124, 125, 135, 150, 250, 300, 500,
                  600, 800, 900, 1000, 1200, 8000]
DBM_REFERENCE_DEFAULT = 600

TRIGGER_SOURCES = [("IMM", N_("Internal (immediate)")),
                   ("EXT", N_("External (Ext Trig jack, rear panel)")),
                   ("BUS", N_("Software (*TRG)"))]

# ------------------------------------------------- PC-side evaluation
CONV_NONE, CONV_LINEAR, CONV_PER_LENGTH = "NONE", "LINEAR", "PER_LENGTH"
CONVERSION_LABELS = {
    CONV_NONE: N_("None"),
    CONV_LINEAR: N_("Linear: y = factor · x + offset (custom unit)"),
    CONV_PER_LENGTH: N_("Per length: value ÷ cable length (e.g. Ω/m)"),
}
# Confidence level for the measurement uncertainty (two-sided, Student t).
CONFIDENCE_LEVELS = [(68.27, N_("68.3 % (1 σ)")), (95.0, N_("95 %")), (99.0, N_("99 %"))]
CONFIDENCE_DEFAULT = 68.27
SIGNAL_FREQUENCY_DEFAULT = 50.0    # Hz, for the AC accuracy specification


@dataclass(frozen=True)
class Function:
    key: str                 # SCPI function name used with CONFigure
    label: str               # German source text, shown with tr()
    short: str
    unit: str
    kind: str                # 'dc' | 'ac' | 'freq' | 'fixed'
    ranges: tuple = ()
    range_prefix: str = ""   # SENSe subsystem for :RANGe / :NPLC
    math: frozenset = frozenset()
    impedance: bool = False  # INPut:IMPedance:AUTO applies
    autozero: bool = False   # ZERO:AUTO selectable (FRES/ratio: always on)
    ac_filter: bool = False
    range_is_input_voltage: bool = False
    hint: str = ""
    example: float = 1.0     # typical reading for the resolution preview


_ALL_MATH = frozenset({MATH_NONE, MATH_NULL, MATH_MINMAX, MATH_LIMIT})
_VOLT_MATH = _ALL_MATH | {MATH_DB, MATH_DBM}

FUNCTIONS: dict[str, Function] = {f.key: f for f in [
    Function("VOLT:DC", N_("DC voltage (DCV)"), "DCV", "V", "dc", tuple(DCV_RANGES),
             "VOLT:DC", _VOLT_MATH, impedance=True, autozero=True, example=5.0021347),
    Function("VOLT:AC", N_("AC voltage (ACV, true RMS)"), "ACV", "V", "ac",
             tuple(ACV_RANGES), "VOLT:AC", _VOLT_MATH, ac_filter=True, example=0.7071234),
    Function("CURR:DC", N_("DC current (DCI)"), "DCI", "A", "dc", tuple(DCI_RANGES),
             "CURR:DC", _ALL_MATH, autozero=True,
             hint=N_("Use the I and LO inputs (max. 3 A)."), example=0.0123456),
    Function("CURR:AC", N_("AC current (ACI, true RMS)"), "ACI", "A", "ac", tuple(ACI_RANGES),
             "CURR:AC", _ALL_MATH, ac_filter=True,
             hint=N_("Use the I and LO inputs (max. 3 A)."), example=0.5123456),
    Function("RES", N_("Resistance 2-wire (Ω2W)"), "Ω2W", "Ω", "dc", tuple(OHM_RANGES),
             "RES", _ALL_MATH, autozero=True, example=108.644630),
    Function("FRES", N_("Resistance 4-wire (Ω4W)"), "Ω4W", "Ω", "dc", tuple(OHM_RANGES),
             "FRES", _ALL_MATH,
             hint=N_("Also connect HI/LO Sense. Autozero is always on."),
             example=108.644630),
    Function("FREQ", N_("Frequency"), "FREQ", "Hz", "freq", tuple(ACV_RANGES),
             "FREQ", _ALL_MATH, range_is_input_voltage=True,
             hint=N_("Range = input voltage range. Measures 3 Hz … 300 kHz."),
             example=1000.01234),
    Function("PER", N_("Period"), "PER", "s", "freq", tuple(ACV_RANGES),
             "PER", _ALL_MATH, range_is_input_voltage=True,
             hint=N_("Range = input voltage range."), example=0.000999987654),
    Function("VOLT:DC:RAT", N_("Voltage ratio DCV:DCV"), "RATIO", "", "dc",
             tuple(DCV_RANGES), "VOLT:DC", frozenset({MATH_NONE, MATH_MINMAX, MATH_LIMIT}),
             impedance=True,
             hint=N_("Reference (max. ±12 V) on HI/LO Sense. Autozero is always on."),
             example=0.49998765),
    Function("CONT", N_("Continuity test"), "CONT", "Ω", "fixed",
             hint=N_("Fixed 1 kΩ range. Beeps below the threshold (default 10 Ω). The threshold "
                     "can only be set on the instrument (Shift > Menu Recall)."),
             example=0.4321),
    Function("DIOD", N_("Diode test"), "DIODE", "V", "fixed",
             hint=N_("Test current 1 mA, range 1 V. Beeps at 0.3 … 0.8 V."),
             example=0.587312),
]}

FUNCTION_DEFAULT = "VOLT:DC"

# Functions grouped by measured quantity, in display order (selection list, live keys).
FUNCTION_GROUPS = [
    (N_("Voltage"), ("VOLT:DC", "VOLT:AC", "VOLT:DC:RAT")),
    (N_("Current"), ("CURR:DC", "CURR:AC")),
    (N_("Resistance"), ("RES", "FRES")),
    (N_("Frequency & time"), ("FREQ", "PER")),
    (N_("Test functions"), ("CONT", "DIOD")),
]
FUNCTION_ORDER = [key for _, keys in FUNCTION_GROUPS for key in keys]


def is_loggable(config: "DeviceConfig") -> bool:
    """Continuity and diode test are front-panel modes: the instrument decides by its own
    threshold and beeps. They are not logged in the measurement plan, only switched to
    ("Switch instrument to this mode") or watched in live mode."""
    return config.func.kind != "fixed"


def not_loggable_text(configs) -> str:
    """Explanation for the plan summary; '' if every configuration can be logged."""
    names = list(dict.fromkeys(tr(c.func.label) for c in configs if not is_loggable(c)))
    if not names:
        return ""
    return tr("⚠ {functions}: not logged in the measurement plan. Use \"Switch instrument to "
              "this mode\" (front panel with beeper) or the live mode. To log a resistance, "
              "choose resistance 2-wire or 4-wire.", functions=", ".join(names))


def digits_text(digits: int) -> str:
    return tr("{n}½ digits", n=digits)


@dataclass
class DeviceConfig:
    """User settings for one instrument."""

    function: str = FUNCTION_DEFAULT
    range: object = AUTO               # numeric range or AUTO
    dc_resolution: str = DC_RESOLUTION_DEFAULT
    ac_resolution: str = AC_RESOLUTION_DEFAULT
    autozero: str = "ON"
    high_impedance: bool = False
    ac_filter: int = AC_FILTER_DEFAULT
    gate_time: float = GATE_DEFAULT
    math: str = MATH_NONE
    null_offset: float | None = None   # None: first reading becomes the offset
    db_reference: float | None = None  # None: first reading becomes the reference
    dbm_reference: int = DBM_REFERENCE_DEFAULT
    limit_lower: float = 0.0
    limit_upper: float = 1.0
    trigger_source: str = "IMM"
    trigger_delay: float | None = None  # None = automatic delay
    samples: int = 1                    # readings averaged per data point
    display_on: bool = True
    beeper_on: bool = True
    label: str = ""                     # measured object, e.g. "Rot 1"
    # PC-side evaluation
    conversion: str = CONV_NONE
    conv_factor: float = 1.0
    conv_offset: float = 0.0
    conv_unit: str = ""
    conv_length: float = 1.0           # metres, for CONV_PER_LENGTH
    uncertainty: bool = True           # calculate the measurement uncertainty u
    confidence: float = CONFIDENCE_DEFAULT   # % (two-sided)
    spec_period: str = "1y"            # accuracy specification: 24h / 90d / 1y
    signal_frequency: float = SIGNAL_FREQUENCY_DEFAULT  # Hz, AC functions

    @property
    def func(self) -> Function:
        return FUNCTIONS[self.function]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceConfig":
        # Unknown keys (settings of removed features, e.g. the tolerance check) are ignored.
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        config = cls(**known)
        if config.function not in FUNCTIONS:
            config.function = FUNCTION_DEFAULT
        if config.conversion not in CONVERSION_LABELS:  # e.g. the removed Pt100 conversion
            config.conversion = CONV_NONE
        if config.confidence not in [level for level, _ in CONFIDENCE_LEVELS]:
            config.confidence = CONFIDENCE_DEFAULT
        return config

    # ---------------------------------------------------- derived properties
    @property
    def digits(self) -> int:
        """Resolution in full digits (4, 5 or 6, each plus a ½ digit)."""
        kind = self.func.kind
        if kind == "dc":
            return _lookup(DC_RESOLUTIONS, self.dc_resolution)[3]
        if kind == "ac":
            return _lookup(AC_RESOLUTIONS, self.ac_resolution)[2]
        if kind == "freq":
            return next((d for g, _, d in GATE_TIMES if g == self.gate_time), 5)
        return 5

    @property
    def nplc(self) -> float | None:
        return _lookup(DC_RESOLUTIONS, self.dc_resolution)[2] if self.func.kind == "dc" else None

    @property
    def unit(self) -> str:
        if self.math == MATH_DB:
            return "dB"
        if self.math == MATH_DBM:
            return "dBm"
        return self.func.unit

    def range_label(self) -> str:
        func = self.func
        if func.kind == "fixed":
            return tr("1 kΩ (fixed)") if func.key == "CONT" else tr("1 V (fixed)")
        if self.range == AUTO:
            return tr("Auto")
        return next((lbl for lbl, v in func.ranges if v == self.range), str(self.range))

    def resolution_label(self) -> str:
        kind = self.func.kind
        if kind == "dc":
            key, speed, nplc, digits = _lookup(DC_RESOLUTIONS, self.dc_resolution)
            return f"{digits_text(digits)} · {tr(speed)} ({localize_number(f'{nplc:g}')} NPLC)"
        if kind == "ac":
            return digits_text(self.digits)
        if kind == "freq":
            gate = next((lbl for g, lbl, _ in GATE_TIMES if g == self.gate_time), "")
            return f"{tr('Gate time')} {gate} · {digits_text(self.digits)}"
        return ""

    def summary(self) -> dict:
        """Settings as readable key/value pairs for export headers."""
        func = self.func
        items = {tr('Function'): tr(func.label), tr("Range"): self.range_label()}
        if func.kind != "fixed":
            items[tr("Resolution")] = self.resolution_label()
        if func.autozero:
            items[tr("Autozero")] = tr(dict(AUTOZERO_CHOICES)[self.autozero])
        if func.impedance:
            items[tr("Input resistance")] = tr(dict(IMPEDANCE_CHOICES)[self.high_impedance])
        if func.ac_filter:
            items[tr("AC filter")] = f"{self.ac_filter} Hz"
        if self.math != MATH_NONE:
            items[tr("Math (instrument)")] = tr(MATH_LABELS[self.math])
            if self.math == MATH_NULL:
                items[tr("Null offset")] = (tr("first reading") if self.null_offset is None
                                            else f"{self.null_offset:g}")
            if self.math in (MATH_DB, MATH_DBM):
                items[tr("dBm reference")] = f"{self.dbm_reference} Ω"
            if self.math == MATH_DB:
                items[tr("dB reference")] = (tr("first reading") if self.db_reference is None
                                            else f"{self.db_reference:g} dBm")
            if self.math == MATH_LIMIT:
                items[tr("Limits")] = f"{self.limit_lower:g} … {self.limit_upper:g}"
        items[tr("Trigger")] = tr(dict(TRIGGER_SOURCES)[self.trigger_source])
        items[tr("Trigger delay")] = (tr("automatic") if self.trigger_delay is None
                                            else f"{self.trigger_delay:g} s")
        if self.samples > 1:
            items[tr("Averaging")] = tr("{n} readings per point", n=self.samples)
        if self.conversion != CONV_NONE:
            items[tr("Conversion")] = tr(CONVERSION_LABELS[self.conversion])
            if self.conversion == CONV_LINEAR:
                items[tr("Formula")] = (f"y = {self.conv_factor:g} · x + {self.conv_offset:g} "
                                       f"{self.conv_unit}")
            if self.conversion == CONV_PER_LENGTH:
                items[tr("Cable length")] = f"{self.conv_length:g} m"
        from .specs import SPEC_PERIODS
        if not self.uncertainty:
            items[tr("Measurement uncertainty")] = tr("not calculated")
            return items
        items[tr("Confidence level")] = tr(dict(CONFIDENCE_LEVELS)[self.confidence])
        items[tr("Accuracy specification")] = tr(dict(SPEC_PERIODS).get(
            self.spec_period, SPEC_PERIODS[-1][1]))
        if self.func.kind == "ac":
            items[tr("Signal frequency")] = f"{self.signal_frequency:g} Hz"
        return items


def _lookup(table, key):
    for row in table:
        if row[0] == key:
            return row
    return table[-1]


def scpi_number(value) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Invalid number: {value!r}")
    return f"{number:.10g}"


def validate(config: DeviceConfig) -> list[str]:
    """Return human-readable problems; an empty list means valid."""
    problems = []
    func = config.func
    if config.math not in func.math and not (func.kind == "fixed" and config.math == MATH_NONE):
        problems.append(tr("{math} is not available for {function}.",
                           math=tr(MATH_LABELS[config.math]), function=tr(func.label)))
    if func.kind != "fixed" and config.range != AUTO:
        if config.range not in [v for _, v in func.ranges]:
            problems.append(tr("Invalid range."))
    if config.math == MATH_LIMIT and config.limit_lower > config.limit_upper:
        problems.append(tr("Lower limit is greater than the upper limit."))
    if config.math == MATH_DBM and config.dbm_reference not in DBM_REFERENCES:
        problems.append(tr("Invalid dBm reference."))
    if not 1 <= config.samples <= 50000:
        problems.append(tr("Readings per point: 1 … 50000."))
    if config.trigger_delay is not None and not 0 <= config.trigger_delay <= 3600:
        problems.append(tr("Trigger delay: 0 … 3600 s."))
    if config.conversion == CONV_PER_LENGTH and config.conv_length <= 0:
        problems.append(tr("The cable length must be greater than 0."))
    if func.kind == "ac" and not 3 <= config.signal_frequency <= 300e3:
        problems.append(tr("Signal frequency: 3 Hz … 300 kHz."))
    return problems


def configuration_commands(config: DeviceConfig) -> list[str]:
    """Translate settings into the SCPI command sequence (CONFigure first)."""
    problems = validate(config)
    if problems:
        raise ValueError(" ".join(problems))
    func = config.func
    cmds: list[str] = []
    auto = config.range == AUTO

    if func.kind == "fixed":
        cmds.append(f"CONF:{func.key}")
    elif func.kind == "dc":
        cmds.append(f"CONF:{func.key} {'DEF' if auto else scpi_number(config.range)}")
        if auto:
            cmds.append(f"{func.range_prefix}:RANG:AUTO ON")
        # Ratio uses the DC voltage subsystem for range and NPLC.
        cmds.append(f"{func.range_prefix}:NPLC {scpi_number(config.nplc)}")
        if func.autozero:
            cmds.append(f"ZERO:AUTO {config.autozero}")
        if func.impedance:
            cmds.append(f"INP:IMP:AUTO {'ON' if config.high_impedance else 'OFF'}")
    elif func.kind == "ac":
        digits = config.digits
        if auto:
            keyword = {4: "MAX", 5: "DEF", 6: "MIN"}[digits]
            cmds.append(f"CONF:{func.key} DEF,{keyword}")
            cmds.append(f"{func.range_prefix}:RANG:AUTO ON")
        else:
            resolution = float(config.range) * 10.0 ** (-digits)
            cmds.append(f"CONF:{func.key} {scpi_number(config.range)},{scpi_number(resolution)}")
        cmds.append(f"DET:BAND {config.ac_filter}")
    elif func.kind == "freq":
        cmds.append(f"CONF:{func.key}")
        if auto:
            cmds.append(f"{func.key}:VOLT:RANG:AUTO ON")
        else:
            cmds.append(f"{func.key}:VOLT:RANG {scpi_number(config.range)}")
        cmds.append(f"{func.key}:APER {scpi_number(config.gate_time)}")

    # Triggering. One READ? returns `samples` readings.
    cmds.append(f"TRIG:SOUR {config.trigger_source}")
    if config.trigger_delay is None:
        cmds.append("TRIG:DEL:AUTO ON")
    else:
        cmds.append(f"TRIG:DEL {scpi_number(config.trigger_delay)}")
    cmds.append("TRIG:COUN 1")
    cmds.append(f"SAMP:COUN {int(config.samples)}")

    # Math must come after CONFigure (which switches math off). The math
    # state must be ON before its registers are written (manual p. 125).
    if config.math != MATH_NONE:
        if config.math in (MATH_DB, MATH_DBM):
            cmds.append(f"CALC:DBM:REF {config.dbm_reference}")
        cmds.append(f"CALC:FUNC {config.math}")
        cmds.append("CALC:STAT ON")
        if config.math == MATH_NULL and config.null_offset is not None:
            cmds.append(f"CALC:NULL:OFFS {scpi_number(config.null_offset)}")
        if config.math == MATH_DB and config.db_reference is not None:
            cmds.append(f"CALC:DB:REF {scpi_number(config.db_reference)}")
        if config.math == MATH_LIMIT:
            cmds.append(f"CALC:LIM:LOW {scpi_number(config.limit_lower)}")
            cmds.append(f"CALC:LIM:UPP {scpi_number(config.limit_upper)}")
    else:
        cmds.append("CALC:STAT OFF")

    # Front-panel modes (continuity, diode) always need the display.
    display = config.display_on or config.func.kind == "fixed"
    cmds.append("DISP ON" if display else "DISP OFF")
    cmds.append(f"SYST:BEEP:STAT {'ON' if config.beeper_on else 'OFF'}")
    return cmds


def estimated_reading_time(config: DeviceConfig, line_frequency: float = 50.0,
                           worst_case: bool = False) -> float:
    """Typical (or worst-case) time for one READ? including RS-232 transfer."""
    func = config.func
    per_sample = 0.05
    if func.kind == "dc":
        per_sample = config.nplc / line_frequency
        if (func.autozero and config.autozero == "ON") or func.key in ("FRES", "VOLT:DC:RAT"):
            per_sample *= 2.2
    elif func.kind == "ac":
        per_sample = 0.4
    elif func.kind == "freq":
        per_sample = config.gate_time + 0.05
    delay = config.trigger_delay
    if delay is None:  # automatic delays, manual p. 81
        if func.ac_filter:
            delay = {3: 7.0, 20: 1.0, 200: 0.6}[config.ac_filter]
        elif func.kind == "freq":
            delay = 1.0
        else:
            delay = 0.0015
    autorange = 0.0
    if worst_case and config.range == AUTO and func.kind != "fixed":
        autorange = 0.8 + (1.0 if func.kind == "freq" else 0.0)
    transfer = 0.06 + 0.02 * config.samples
    return config.samples * (per_sample + 0.01) + delay + autorange + transfer


def read_timeout(config: DeviceConfig) -> float:
    """Serial timeout for one READ? with a generous safety margin."""
    return max(5.0, estimated_reading_time(config, worst_case=True) * 2.0 + 3.0)


# ------------------------------------------------------------------ formatting
def active_range(config: DeviceConfig, value: float) -> float | None:
    """Range the reading was taken in (estimated from the value for autorange)."""
    func = config.func
    if func.kind == "fixed":
        return 1000.0 if func.key == "CONT" else 1.0
    if func.kind not in ("dc", "ac") or func.key == "VOLT:DC:RAT" or config.math in (
            MATH_DB, MATH_DBM):
        return None
    if config.range != AUTO:
        return float(config.range)
    # Autorange switches up at 120 % of a range.
    for _, limit in func.ranges:
        if abs(value) <= limit * 1.2:
            return float(limit)
    return float(func.ranges[-1][1])


def resolution_step(config: DeviceConfig, value: float) -> float | None:
    """Smallest displayed step, as on the front panel (e.g. 10 V range, 6½ → 10 µV)."""
    rng = active_range(config, value)
    return None if rng is None else rng * 10.0 ** (-config.digits)


_PREFIXES = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n")]


def _prefix_for(magnitude: float):
    for factor, symbol in _PREFIXES:
        if magnitude >= factor * 0.9999995:
            return factor, symbol
    return _PREFIXES[-1]


def format_value(value: float | None, unit: str, step: float | None = None,
                 significant: int = 6, localized: bool = True) -> str:
    """Format with SI prefix.

    With ``step`` the value is rounded to the instrument's resolution
    (front-panel digits); otherwise ``significant`` digits are shown.
    """
    if value is None or not math.isfinite(value):
        return "OVLD"
    if unit in ("dB", "dBm", "", "°C") or unit not in ("V", "A", "Ω", "Hz", "s"):
        scale, prefix = 1.0, ""
    else:
        reference = abs(value) if step is None or abs(value) >= step * 1000 else step * 1e4
        scale, prefix = _prefix_for(reference) if reference > 0 else (1.0, "")
    scaled = value / scale
    if step is not None:
        decimals = max(0, int(round(-math.log10(step / scale))))
    else:
        integer_digits = max(1, int(math.floor(math.log10(abs(scaled)))) + 1) if scaled else 1
        decimals = max(0, significant - integer_digits)
    text = f"{scaled:.{decimals}f}"
    if float(text) == 0:
        text = text.lstrip("-")
    if localized:
        text = localize_number(text)
    return f"{text} {prefix}{unit}".rstrip()


def format_reading(config: DeviceConfig, value: float | None, localized: bool = True) -> str:
    """A reading as the instrument would display it with the chosen digits."""
    if value is None:
        return "OVLD"
    return format_value(value, config.unit, resolution_step(config, value), config.digits + 1,
                        localized)


def number_text(config: DeviceConfig, value: float | None, decimal: str = ".") -> str:
    """Plain number (base unit) at the instrument resolution, for CSV files."""
    if value is None or not math.isfinite(value):
        return ""
    step = resolution_step(config, value)
    if step is not None:
        text = f"{value:.{max(0, int(round(-math.log10(step))))}f}"
        if float(text) == 0:
            text = text.lstrip("-")
    else:
        text = f"{value:.{config.digits + 1}g}"
    return text.replace(".", decimal) if decimal != "." else text


def preview_value(config: DeviceConfig, measured: float | None = None) -> float:
    """Value used to show how a reading will look: last reading or a typical one."""
    if measured is not None and math.isfinite(measured):
        return measured
    func = config.func
    if config.range != AUTO and func.ranges:
        return float(config.range) * 0.5432109876
    return func.example


def is_overload(value: float) -> bool:
    return not math.isfinite(value) or abs(value) >= 9.0e37
