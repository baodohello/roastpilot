from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.interpolate import PchipInterpolator


@dataclass(frozen=True)
class Milestone:
    time_s: float
    temp_c: float


@dataclass(frozen=True)
class TargetRoR:
    time_s: np.ndarray
    ror_c_per_min: np.ndarray
    bt_c: np.ndarray
    milestones: tuple[Milestone, ...]
    ror_start_time_s: float = 0.0


def smoothstep(x: np.ndarray) -> np.ndarray:
    return 3.0 * x**2 - 2.0 * x**3


def _make_phase(start: Milestone, end: Milestone, points: int = 150, end_ratio: float = .65) -> tuple[np.ndarray, np.ndarray]:
    """Create a temperature-consistent phase; negative deltas create a falling RoR."""
    duration_s, delta_temp = end.time_s - start.time_s, end.temp_c - start.temp_c
    if duration_s <= 0:
        raise ValueError("Milestone times must be strictly increasing.")
    if delta_temp == 0:
        raise ValueError("Consecutive milestone temperatures cannot be equal.")
    x = np.linspace(0.0, 1.0, points)
    shape = 1.0 - (1.0 - end_ratio) * smoothstep(x)
    area = np.trapezoid(shape, x) * duration_s / 60.0
    return np.linspace(start.time_s, end.time_s, points), shape * delta_temp / area


def generate_target_ror(
    de_time_s: float, de_temp_c: float, fc_time_s: float, fc_temp_c: float,
    drop_time_s: float, drop_temp_c: float, points_per_phase: int = 150,
    charge_temp_c: float = 25.0, turn_time_s: float | None = None,
    turn_temp_c: float | None = None,
) -> TargetRoR:
    """Build a Charge → [Turn] → DE → FC → Drop RoR profile.

    A turning point is optional for compatibility, but a high charge reading
    should supply both its planned time and temperature.
    """
    charge = Milestone(0.0, float(charge_temp_c))
    de, fc, drop = Milestone(float(de_time_s), float(de_temp_c)), Milestone(float(fc_time_s), float(fc_temp_c)), Milestone(float(drop_time_s), float(drop_temp_c))
    if (turn_time_s is None) != (turn_temp_c is None):
        raise ValueError("Provide both turning-point time and temperature.")
    turn = Milestone(float(turn_time_s), float(turn_temp_c)) if turn_time_s is not None else None
    milestones = (charge, turn, de, fc, drop) if turn else (charge, de, fc, drop)
    if any(a.time_s >= b.time_s for a, b in zip(milestones, milestones[1:])):
        raise ValueError("Time must satisfy: Charge < Turn < DE < FC < Drop.")
    if turn:
        if not turn.temp_c < charge.temp_c or not turn.temp_c < de.temp_c:
            raise ValueError("Turning-point temperature must be below Charge and Dry End BT.")
    elif charge.temp_c >= de.temp_c:
        raise ValueError("Charge BT must be below Dry End without a turning point.")
    if not de.temp_c < fc.temp_c < drop.temp_c:
        raise ValueError("Temperature must satisfy: DE < FC < Drop.")

    # Charge temperature belongs to the roaster, not to the bean-temperature
    # target. With a turning point, the useful BT/RoR target therefore begins
    # at Turn and follows the rising bean-temperature milestones only.
    profile_milestones = (turn, de, fc, drop) if turn else (charge, de, fc, drop)
    # A single shape-preserving cubic temperature curve avoids artificial RoR
    # steps at milestone boundaries. Its derivative is the target RoR.
    knot_time_min = np.array([milestone.time_s / 60.0 for milestone in profile_milestones])
    knot_temp_c = np.array([milestone.temp_c for milestone in profile_milestones])
    temperature_curve = PchipInterpolator(knot_time_min, knot_temp_c)
    time_parts = [
        np.linspace(start.time_s, end.time_s, points_per_phase)
        for start, end in zip(profile_milestones, profile_milestones[1:])
    ]
    time_s = np.concatenate([
        part if index == 0 else part[1:]
        for index, part in enumerate(time_parts)
    ])
    time_min = time_s / 60.0
    # BT is the source of truth. The RoR shown on the right axis is the
    # analytic derivative of this exact same displayed BT trajectory.
    bt_c = temperature_curve(time_min)
    ror = temperature_curve.derivative()(time_min)
    return TargetRoR(
        time_s=time_s,
        ror_c_per_min=ror,
        bt_c=bt_c,
        milestones=milestones,
        ror_start_time_s=profile_milestones[0].time_s,
    )


def parse_mmss(value: str) -> float:
    value = value.strip()
    if ":" not in value:
        raise ValueError(f"Invalid time '{value}'. Use MM:SS.")
    minutes, seconds = value.split(":", 1)
    try:
        minutes, seconds = float(minutes), float(seconds)
    except ValueError as error:
        raise ValueError(f"Invalid time '{value}'. Use MM:SS.") from error
    if minutes < 0 or not 0 <= seconds < 60:
        raise ValueError("Seconds must be between 0 and 59; time cannot be negative.")
    return minutes * 60 + seconds


def validate_milestones(*milestones: Milestone) -> None:
    """Legacy helper for strictly rising milestone lists."""
    if any(a.time_s >= b.time_s for a, b in zip(milestones, milestones[1:])):
        raise ValueError("Milestone times must be strictly increasing.")
    if any(a.temp_c >= b.temp_c for a, b in zip(milestones, milestones[1:])):
        raise ValueError("Milestone temperatures must be strictly increasing.")
