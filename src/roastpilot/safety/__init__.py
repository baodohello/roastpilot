from __future__ import annotations


def output_is_safe(percent: float) -> bool:
    return 0.0 <= percent <= 100.0


def clamp_output(percent: float) -> float:
    return max(0.0, min(100.0, percent))
