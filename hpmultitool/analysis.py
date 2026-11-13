"""PC-side evaluation of readings: conversion, tolerance check, statistics.

The instrument's own math (null, dB, limit, ...) runs inside the 34401A.
These functions run on the PC and are applied to every recorded value.
"""

from __future__ import annotations

import math
import statistics

from .functions import (CONV_LINEAR, CONV_NONE, CONV_PER_LENGTH, CONV_PT100, CONV_PT1000,
                        TOL_ABSOLUTE, TOL_NONE, TOL_PERCENT, TOL_RANGE, DeviceConfig)

# IEC 60751 coefficients (Callendar-Van Dusen)
_A, _B, _C = 3.9083e-3, -5.775e-7, -4.183e-12

VERDICT_PASS, VERDICT_FAIL = "PASS", "FAIL"


def platinum_temperature(resistance: float, r0: float) -> float:
    """Temperature in °C of a Pt100/Pt1000 sensor (−200 … 850 °C)."""
    ratio = resistance / r0
    if ratio >= 1.0:
        return (-_A + math.sqrt(_A * _A - 4 * _B * (1 - ratio))) / (2 * _B)
    t = (ratio - 1) / _A  # Newton iteration for the range below 0 °C
    for _ in range(20):
        r = 1 + _A * t + _B * t * t + _C * (t - 100) * t ** 3
        dr = _A + 2 * _B * t + _C * (4 * t ** 3 - 300 * t * t)
        step = (r - ratio) / dr
        t -= step
        if abs(step) < 1e-9:
            break
    return t


def derived_unit(config: DeviceConfig) -> str:
    conv = config.conversion
    if conv == CONV_LINEAR:
        return config.conv_unit.strip()
    if conv == CONV_PER_LENGTH:
        return f"{config.unit}/m"
    if conv in (CONV_PT100, CONV_PT1000):
        return "°C"
    return ""


def derive(config: DeviceConfig, value: float | None) -> float | None:
    """Converted value, or None without conversion / without a valid reading."""
    if value is None or config.conversion == CONV_NONE:
        return None
    conv = config.conversion
    try:
        if conv == CONV_LINEAR:
            return config.conv_factor * value + config.conv_offset
        if conv == CONV_PER_LENGTH:
            return value / config.conv_length
        if conv == CONV_PT100:
            return platinum_temperature(value, 100.0)
        if conv == CONV_PT1000:
            return platinum_temperature(value, 1000.0)
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    return None


def verdict(config: DeviceConfig, value: float | None, derived: float | None) -> str:
    """PASS/FAIL against the tolerance; '' if no tolerance is set."""
    if config.tolerance == TOL_NONE:
        return ""
    checked = derived if config.conversion != CONV_NONE else value
    if checked is None:
        return VERDICT_FAIL
    if config.tolerance == TOL_PERCENT:
        low = config.tol_nominal - abs(config.tol_nominal) * config.tol_value / 100
        high = config.tol_nominal + abs(config.tol_nominal) * config.tol_value / 100
    elif config.tolerance == TOL_ABSOLUTE:
        low, high = config.tol_nominal - config.tol_value, config.tol_nominal + config.tol_value
    elif config.tolerance == TOL_RANGE:
        low, high = config.tol_low, config.tol_high
    else:
        return ""
    return VERDICT_PASS if low <= checked <= high else VERDICT_FAIL


def statistics_of(values: list[float], times: list[float] | None = None) -> dict:
    """min, max, mean, std, peak-peak and drift per minute (linear regression)."""
    if not values:
        return {"count": 0}
    result = {"count": len(values), "min": min(values), "max": max(values),
              "mean": statistics.fmean(values)}
    result["std"] = statistics.stdev(values) if len(values) > 1 else 0.0
    result["pp"] = result["max"] - result["min"]
    if times is not None and len(values) >= 3 and max(times) - min(times) > 0:
        mean_t = statistics.fmean(times)
        sxx = sum((t - mean_t) ** 2 for t in times)
        sxy = sum((t - mean_t) * (v - result["mean"]) for t, v in zip(times, values))
        result["drift"] = sxy / sxx * 60.0 if sxx else 0.0
    return result


def moving_average(values: list[float], window: int) -> list[float]:
    if window <= 1 or not values:
        return list(values)
    out, total = [], 0.0
    for i, v in enumerate(values):
        total += v
        if i >= window:
            total -= values[i - window]
        out.append(total / min(i + 1, window))
    return out
