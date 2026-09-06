from __future__ import annotations


class Watchdog:
    """Detect stale telemetry: feed() on each reading, is_expired() to check."""

    def __init__(self, timeout_s: float) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.timeout_s = timeout_s
        self._last_feed_s: float | None = None

    def feed(self, now_s: float) -> None:
        if self._last_feed_s is not None and now_s < self._last_feed_s:
            raise ValueError("now_s must be non-decreasing")
        self._last_feed_s = now_s

    def age_s(self, now_s: float) -> float | None:
        if self._last_feed_s is None:
            return None
        return now_s - self._last_feed_s

    def is_expired(self, now_s: float) -> bool:
        age = self.age_s(now_s)
        if age is None:
            return True
        return age > self.timeout_s

    def reset(self) -> None:
        self._last_feed_s = None
