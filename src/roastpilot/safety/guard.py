from __future__ import annotations


class BurnerGuard:
    """Failsafe output guard for a burner setpoint.

    Clamps to absolute limits, limits the slew rate, cuts output to zero when
    inputs go stale, and latches to zero after an emergency stop until reset().
    """

    def __init__(
        self,
        output_min: float = 0.0,
        output_max: float = 100.0,
        max_slew_per_s: float = 50.0,
        stale_timeout_s: float = 5.0,
    ) -> None:
        if output_min > output_max:
            raise ValueError("output_min must not exceed output_max")
        if max_slew_per_s <= 0:
            raise ValueError("max_slew_per_s must be positive")
        if stale_timeout_s <= 0:
            raise ValueError("stale_timeout_s must be positive")
        self.output_min = output_min
        self.output_max = output_max
        self.max_slew_per_s = max_slew_per_s
        self.stale_timeout_s = stale_timeout_s
        self._last_output: float = 0.0
        self._last_update_s: float | None = None
        self._e_stop: bool = False

    def emergency_stop(self) -> None:
        """Latch the guard to zero until reset()."""
        self._e_stop = True

    @property
    def tripped(self) -> bool:
        return self._e_stop

    def reset(self) -> None:
        self._e_stop = False
        self._last_output = 0.0
        self._last_update_s = None

    def update(self, requested: float, now_s: float) -> float:
        """Return the safe output for `requested` at time `now_s`."""
        if self._e_stop:
            self._last_output = 0.0
            return 0.0
        if self._last_update_s is not None:
            dt = now_s - self._last_update_s
            if dt < 0:
                raise ValueError("now_s must be non-decreasing")
            if dt > self.stale_timeout_s:
                self._last_output = 0.0
                self._last_update_s = now_s
                return 0.0
        else:
            dt = 0.0
        clamped = max(self.output_min, min(self.output_max, requested))
        if dt > 0:
            max_step = self.max_slew_per_s * dt
            clamped = max(
                self._last_output - max_step,
                min(self._last_output + max_step, clamped),
            )
        self._last_output = clamped
        self._last_update_s = now_s
        return clamped
