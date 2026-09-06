from __future__ import annotations

from math import exp


class RoastSimulator:
    """First-order plant model: burner % drives an equilibrium RoR with lag."""

    def __init__(
        self,
        ambient_temp_c: float = 25.0,
        gain: float = 0.54,
        ambient_loss: float = 0.20,
        time_constant_s: float = 16.0,
    ) -> None:
        if time_constant_s <= 0:
            raise ValueError("time_constant_s must be positive")
        self.ambient_temp_c = ambient_temp_c
        self.gain = gain
        self.ambient_loss = ambient_loss
        self.time_constant_s = time_constant_s
        self.ror_c_per_min = 0.0

    def step(self, burner_percent: float, bean_temp_c: float, dt_s: float) -> float:
        """Advance one step and return the new RoR in °C/min."""
        if dt_s <= 0:
            raise ValueError("dt_s must be positive")
        equilibrium = self.gain * burner_percent - self.ambient_loss * (
            bean_temp_c - self.ambient_temp_c
        )
        self.ror_c_per_min += (equilibrium - self.ror_c_per_min) * (
            1.0 - exp(-dt_s / self.time_constant_s)
        )
        return self.ror_c_per_min

    def reset(self) -> None:
        self.ror_c_per_min = 0.0
