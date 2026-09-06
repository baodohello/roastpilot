from __future__ import annotations

from roastpilot.safety.guard import BurnerGuard
from roastpilot.safety.watchdog import Watchdog

__all__ = ["BurnerGuard", "Watchdog", "clamp_output"]


def clamp_output(percent: float) -> float:
    return max(0.0, min(100.0, percent))
