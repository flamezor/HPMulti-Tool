"""PC-side evaluation of readings: conversion and measurement result with uncertainty.

The instrument's own math (null, dB, limit, ...) runs inside the 34401A.
Everything here runs on the PC.

Measurement result of a series of n readings (DIN 1319-3, GUM; as taught in the
physics lab courses):

    mean            x̄ = 1/n · Σ xᵢ
    std. deviation  s = √( Σ (xᵢ − x̄)² / (n − 1) )        (empirical, single reading)
    std. error      s(x̄) = s / √n                          (of the mean)
    random part     t · s(x̄)       t: Student factor for n − 1 degrees of freedom
    instrument      h               maximum error from the data sheet (specs.py)
    uncertainty     u = t · s(x̄) + h
    result          x = x̄ ± u, u rounded to two significant digits

At least ``MIN_READINGS`` readings are needed for a meaningful standard
deviation; with fewer readings only h is given and the result is marked as
not valid.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from functools import lru_cache

from .functions import CONV_LINEAR, CONV_NONE, CONV_PER_LENGTH, DeviceConfig
from .i18n import N_, localize_number
from .specs import instrument_error

MIN_READINGS = 4


# --------------------------------------------------------------------- conversion
def derived_unit(config: DeviceConfig) -> str:
    if config.conversion == CONV_LINEAR:
        return config.conv_unit.strip()
    if config.conversion == CONV_PER_LENGTH:
        return f"{config.unit}/m"
    return ""


def conversion_factor(config: DeviceConfig) -> float:
    """Slope of the conversion (both conversions are linear)."""
    if config.conversion == CONV_LINEAR:
        return config.conv_factor
    if config.conversion == CONV_PER_LENGTH:
        return 1.0 / config.conv_length
    return 1.0


def derive(config: DeviceConfig, value: float | None) -> float | None:
    """Converted value, or None without conversion / without a valid reading."""
    if value is None or config.conversion == CONV_NONE:
        return None
    try:
        if config.conversion == CONV_LINEAR:
            return config.conv_factor * value + config.conv_offset
        if config.conversion == CONV_PER_LENGTH:
            return value / config.conv_length
    except (ZeroDivisionError, OverflowError):
        return None
    return None


# --------------------------------------------------------------------- Student t
def _incomplete_beta(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b) (continued fraction)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _incomplete_beta(b, a, 1.0 - x)
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    result = d
    for m in range(1, 300):
        for numerator in (m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
                          -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))):
            d = 1.0 + numerator * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + numerator / c
            c = c if abs(c) > tiny else tiny
            result *= c * d
        if abs(c * d - 1.0) < 1e-14:
            break
    return front * result / a


def _two_sided_probability(t: float, dof: int) -> float:
    """P(|T| ≤ t) for Student's t distribution with ``dof`` degrees of freedom."""
    return 1.0 - _incomplete_beta(dof / 2.0, 0.5, dof / (dof + t * t))


@lru_cache(maxsize=512)
def student_t(confidence: float, n: int) -> float | None:
    """Student factor t for n readings and a two-sided confidence level in percent."""
    if n < 2:
        return None
    dof, target = n - 1, confidence / 100.0
    low, high = 0.0, 1.0
    while _two_sided_probability(high, dof) < target:
        high *= 2.0
    for _ in range(200):
        mid = (low + high) / 2
        if _two_sided_probability(mid, dof) < target:
            low = mid
        else:
            high = mid
        if high - low < 1e-10:
            break
    return (low + high) / 2


# --------------------------------------------------------------------- rounding
def round_significant(value: float, digits: int = 2) -> tuple[Decimal, int]:
    """Round to ``digits`` significant digits, ties to even (4.135 → 4.14, 4.125 → 4.12).

    Returns the rounded number and the exponent of its last digit.
    """
    number = Decimal(repr(value))
    if number == 0:
        return number, 0
    exponent = number.adjusted() - digits + 1
    rounded = number.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_EVEN)
    if rounded.adjusted() > number.adjusted():  # e.g. 9.96 → 10: one digit less needed
        exponent += 1
        rounded = number.quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_EVEN)
    return rounded, exponent


def round_to(value: float, exponent: int) -> Decimal:
    return Decimal(repr(value)).quantize(Decimal(1).scaleb(exponent), rounding=ROUND_HALF_EVEN)


_PREFIXES = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1.0, ""), (1e-3, "m"), (1e-6, "µ"),
             (1e-9, "n"), (1e-12, "p")]
_SI_UNITS = ("V", "A", "Ω", "Hz", "s")


def result_text(mean: float, u: float | None, unit: str) -> str:
    """Measurement result as "(x̄ ± u) unit" with u on two significant digits.

    Both numbers share one SI prefix and end at the same decimal position.
    """
    reference = abs(mean) or abs(u or 0.0)
    scale, prefix = 1.0, ""
    # SI prefixes only for SI units (also per length, e.g. mΩ/m), not for custom units.
    if unit.split("/")[0] in _SI_UNITS and reference:
        for factor, symbol in _PREFIXES:
            if reference >= factor * 0.9995:
                scale, prefix = factor, symbol
                break
        else:
            scale, prefix = _PREFIXES[-1]
    full_unit = f" {prefix}{unit}" if (prefix or unit) else ""
    if u is None or u <= 0:
        return localize_number(f"{mean / scale:.6g}") + full_unit
    u_rounded, exponent = round_significant(u / scale)
    mean_rounded = round_to(mean / scale, exponent)
    places = max(0, -exponent)
    u_text = localize_number(f"{u_rounded:.{places}f}")
    mean_text = localize_number(f"{mean_rounded:.{places}f}")
    return f"({mean_text} ± {u_text}){full_unit}"


# --------------------------------------------------------------------- evaluation
@dataclass
class Evaluation:
    """Statistical evaluation of the valid readings of one instrument and step."""

    n: int = 0
    invalid: int = 0                # overload, timeout or error readings
    mean: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    s: float | None = None          # empirical standard deviation (n − 1)
    sem: float | None = None        # standard deviation of the mean s/√n
    t: float | None = None          # Student factor
    random: float | None = None     # t · s/√n
    h: float | None = None          # instrument error from the data sheet
    u: float | None = None          # measurement uncertainty
    confidence: float = 68.27
    valid: bool = False             # n ≥ MIN_READINGS (and the uncertainty is known)
    notes: list[str] = field(default_factory=list)   # source texts for tr()
    with_uncertainty: bool = True   # False: only mean and scatter (switched off by the user)

    @property
    def spread(self) -> float | None:
        if self.minimum is None:
            return None
        return self.maximum - self.minimum

    @property
    def relative(self) -> float | None:
        """Relative uncertainty u / |x̄| in percent."""
        if self.u is None or not self.mean:
            return None
        return self.u / abs(self.mean) * 100

    def converted(self, config: DeviceConfig) -> "Evaluation | None":
        """The same result after the (linear) conversion; None without conversion."""
        if config.conversion == CONV_NONE or self.mean is None:
            return None
        k = abs(conversion_factor(config))

        def scale(value):
            return None if value is None else value * k

        low, high = derive(config, self.minimum), derive(config, self.maximum)
        return Evaluation(self.n, self.invalid, derive(config, self.mean), min(low, high),
                          max(low, high), scale(self.s), scale(self.sem), self.t,
                          scale(self.random), scale(self.h), scale(self.u), self.confidence,
                          self.valid, list(self.notes), self.with_uncertainty)


def evaluate(values: list[float], config: DeviceConfig, invalid: int = 0) -> Evaluation:
    """Measurement result x̄ ± u of the valid readings ``values``."""
    result = Evaluation(n=len(values), invalid=invalid, confidence=config.confidence,
                        with_uncertainty=config.uncertainty)
    if not values:
        return result
    result.mean = statistics.fmean(values)
    result.minimum, result.maximum = min(values), max(values)
    if len(values) >= 2:
        result.s = statistics.stdev(values)
        result.sem = result.s / math.sqrt(len(values))
    if not config.uncertainty:
        # Only mean and scatter: no t, h or u, so nothing can be "not valid".
        result.valid = True
        return result
    error = instrument_error(config, result.mean)
    if error is not None:
        result.h = error.value
        result.notes += error.notes
    else:
        result.notes.append(N_("Instrument error not specified for these settings – "
                               "u contains only the random part."))
    if result.sem is not None:
        result.t = student_t(config.confidence, len(values))
        result.random = result.t * result.sem
    if len(values) >= MIN_READINGS:
        result.valid = True
        result.u = result.random + (result.h or 0.0)
    else:
        # Too few readings for a standard deviation: only the instrument error (as for a
        # single reading) is given, and the result is marked as not valid.
        result.u = result.h
        result.notes.insert(0, N_("Fewer than 4 readings: the scatter cannot be evaluated."))
    return result


def statistics_of(values: list[float]) -> dict:
    """Running min, max, mean and standard deviation (live display)."""
    if not values:
        return {"count": 0}
    return {"count": len(values), "min": min(values), "max": max(values),
            "mean": statistics.fmean(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0.0}
