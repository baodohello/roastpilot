from __future__ import annotations

import numpy as np

from roastpilot.core.target_ror import TargetRoR


def target_at(target: TargetRoR, time_s: float) -> float | None:
    """Return the interpolated target RoR, or None outside the configured roast."""
    if time_s < target.ror_start_time_s or time_s > target.time_s[-1]:
        return None
    return float(np.interp(time_s, target.time_s, target.ror_c_per_min))
