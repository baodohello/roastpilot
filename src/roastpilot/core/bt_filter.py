from __future__ import annotations

from collections import deque


class RateOfRiseFilter:
    """Estimate RoR from BT readings using a small trailing regression window."""

    def __init__(self, window_s: float = 30.0, minimum_samples: int = 4) -> None:
        if window_s <= 0:
            raise ValueError("window_s must be positive")
        self.window_s = window_s
        self.minimum_samples = minimum_samples
        self._samples: deque[tuple[float, float]] = deque()

    def reset(self) -> None:
        self._samples.clear()

    def add(self, time_s: float, temp_c: float) -> float | None:
        if self._samples and time_s <= self._samples[-1][0]:
            raise ValueError("Readings must have increasing timestamps")
        self._samples.append((time_s, temp_c))
        cutoff = time_s - self.window_s
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        if len(self._samples) < self.minimum_samples:
            return None
        count = len(self._samples)
        mean_t = sum(item[0] for item in self._samples) / count
        mean_temp = sum(item[1] for item in self._samples) / count
        denominator = sum((item[0] - mean_t) ** 2 for item in self._samples)
        if denominator == 0:
            return None
        slope_c_per_s = sum(
            (sample_t - mean_t) * (sample_temp - mean_temp)
            for sample_t, sample_temp in self._samples
        ) / denominator
        return slope_c_per_s * 60.0
