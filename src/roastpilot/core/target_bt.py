from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.interpolate import Akima1DInterpolator, CubicSpline, PchipInterpolator


@dataclass(frozen=True)
class Milestone:
    time_s: float
    temp_c: float


@dataclass(frozen=True)
class TargetProfile:
    """Target bean-temperature line sampled on a uniform time grid."""
    time_s: np.ndarray
    bt_c: np.ndarray
    milestones: tuple[Milestone, ...]
    ror_start_time_s: float = 0.0


BT_FIT_METHODS = ("pchip", "cubic", "akima", "linear", "decline")


def generate_target_bt(
    start_temp_c: float, de_time_s: float, de_temp_c: float,
    fc_time_s: float, fc_temp_c: float, drop_time_s: float, drop_temp_c: float,
    sample_interval_s: float = 1.0, method: str = "pchip",
) -> TargetProfile:
    """Build the target BT line: Turn(start) → DE → FC → Drop, sampled every second.

    `method` selects the fit: pchip (monotone, default), cubic, akima, linear,
    or decline (RoR declines monotonically from the turning point to drop).
    """
    start = Milestone(0.0, float(start_temp_c))
    de = Milestone(float(de_time_s), float(de_temp_c))
    fc = Milestone(float(fc_time_s), float(fc_temp_c))
    drop = Milestone(float(drop_time_s), float(drop_temp_c))
    milestones = (start, de, fc, drop)
    if any(a.time_s >= b.time_s for a, b in zip(milestones, milestones[1:])):
        raise ValueError("Time must satisfy: Turn < DE < FC < Drop.")
    if not start.temp_c < de.temp_c < fc.temp_c < drop.temp_c:
        raise ValueError("Temperature must satisfy: Turn < DE < FC < Drop.")
    if sample_interval_s <= 0:
        raise ValueError("sample_interval_s must be positive.")

    knot_time_min = np.array([milestone.time_s / 60.0 for milestone in milestones])
    knot_temp_c = np.array([milestone.temp_c for milestone in milestones])

    # Uniform one-second BT stream from the turning point to drop.
    time_s = np.arange(0.0, drop.time_s, sample_interval_s)
    time_s = np.append(time_s, drop.time_s)
    if method == "decline":
        bt_c = _bt_declining_ror(start_temp_c, milestones, time_s)
    else:
        bt_c = _fit_bt(time_s, knot_time_min, knot_temp_c, method)
    return TargetProfile(time_s=time_s, bt_c=bt_c, milestones=milestones, ror_start_time_s=0.0)


def _bt_declining_ror(
    start_temp_c: float, milestones: tuple[Milestone, ...], time_s: np.ndarray,
) -> np.ndarray:
    """Build a BT curve whose RoR declines monotonically from turn to drop.

    RoR is piecewise-linear and decreasing; BT is its integral, so it passes
    exactly through the milestone temperatures. The profile must be naturally
    declining (drying ≥ maillard ≥ development average RoR).
    """
    temps = np.array([milestone.temp_c for milestone in milestones])
    times = np.array([milestone.time_s for milestone in milestones])
    durations_min = np.diff(times) / 60.0
    avg_ror = np.diff(temps) / durations_min  # m1, m2, m3 (°C/min)

    if not (avg_ror[0] >= avg_ror[1] >= avg_ror[2] and avg_ror[2] > 0):
        raise ValueError(
            "Declining-RoR fit needs a naturally declining profile: "
            "drying ≥ maillard ≥ development average RoR."
        )

    m1, m2, m3 = avg_ror
    lower = max(m1, m3 - 2.0 * m2 + 2.0 * m1)
    upper = min(2.0 * m1 - m2, 2.0 * m1 - 2.0 * m2 + 2.0 * m3)
    if not (lower < upper):
        raise ValueError(
            "Milestones cannot be met by a declining RoR that stays above zero. "
            "Shorten the development duration or raise the drop temperature."
        )
    r0 = (lower + upper) / 2.0
    r1 = 2.0 * m1 - r0
    r2 = 2.0 * m2 - 2.0 * m1 + r0
    r3 = 2.0 * m3 - 2.0 * m2 + 2.0 * m1 - r0

    knot_min = times / 60.0
    ror = np.interp(time_s / 60.0, knot_min, np.array([r0, r1, r2, r3]))

    # Integrate the piecewise-linear RoR (trapezoid rule is exact here).
    increments = (ror[1:] + ror[:-1]) / 2.0 * (1.0 / 60.0)
    bt = np.concatenate(([float(start_temp_c)], float(start_temp_c) + np.cumsum(increments)))

    # Snap exact milestone temperatures to remove floating-point drift.
    for milestone in milestones:
        index = int(abs(time_s - milestone.time_s).argmin())
        bt[index] = milestone.temp_c
    return bt


def _fit_bt(
    time_s: np.ndarray, knot_time_min: np.ndarray, knot_temp_c: np.ndarray, method: str,
) -> np.ndarray:
    """Evaluate the chosen interpolator over the one-second grid (degC)."""
    x = time_s / 60.0
    if method == "linear":
        return np.interp(x, knot_time_min, knot_temp_c)
    if method == "pchip":
        curve = PchipInterpolator(knot_time_min, knot_temp_c)
    elif method == "cubic":
        curve = CubicSpline(knot_time_min, knot_temp_c)
    elif method == "akima":
        curve = Akima1DInterpolator(knot_time_min, knot_temp_c)
    else:
        raise ValueError(f"Unknown BT fit method: {method!r}. Choose from {BT_FIT_METHODS}.")
    return curve(x)
