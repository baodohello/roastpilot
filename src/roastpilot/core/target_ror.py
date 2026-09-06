from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from roastpilot.core.bt_filter import RateOfRiseFilter
from roastpilot.core.target_bt import Milestone, TargetProfile, generate_target_bt


@dataclass(frozen=True)
class TargetRoR:
    """Target profile plus its derived RoR stream."""
    time_s: np.ndarray
    ror_c_per_min: np.ndarray
    bt_c: np.ndarray
    milestones: tuple[Milestone, ...]
    ror_start_time_s: float = 0.0


def ror_from_bt(profile: TargetProfile, window_s: float = 30.0) -> np.ndarray:
    """Generate the RoR stream from a target BT profile (degC/min)."""
    estimator = RateOfRiseFilter(window_s=window_s)
    values = [estimator.add(float(t), float(bt)) for t, bt in zip(profile.time_s, profile.bt_c)]
    first_valid = next((value for value in values if value is not None), 0.0)
    return np.array(
        [first_valid if value is None else value for value in values],
        dtype=float,
    )


def generate_target_ror(
    start_temp_c: float, de_time_s: float, de_temp_c: float,
    fc_time_s: float, fc_temp_c: float, drop_time_s: float, drop_temp_c: float,
    sample_interval_s: float = 1.0, window_s: float = 30.0, method: str = "pchip",
) -> TargetRoR:
    """Convenience wrapper: build the target BT line and derive its RoR."""
    profile = generate_target_bt(
        start_temp_c, de_time_s, de_temp_c, fc_time_s, fc_temp_c,
        drop_time_s, drop_temp_c, sample_interval_s, method=method,
    )
    ror = ror_from_bt(profile, window_s=window_s)
    return TargetRoR(
        time_s=profile.time_s,
        ror_c_per_min=ror,
        bt_c=profile.bt_c,
        milestones=profile.milestones,
        ror_start_time_s=profile.ror_start_time_s,
    )
