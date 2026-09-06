from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GasEnvelope:
    """Burner min/max limits for a roast phase (percent)."""

    min_burner: float = 0.0
    max_burner: float = 100.0

    def clamp(self, value: float) -> float:
        return max(self.min_burner, min(self.max_burner, value))


@dataclass
class ControlPolicy:
    """Phase gas envelopes and gain shaping for the RoR-following PID."""

    drying: GasEnvelope = field(default_factory=lambda: GasEnvelope(30.0, 100.0))
    maillard: GasEnvelope = field(default_factory=lambda: GasEnvelope(20.0, 90.0))
    development: GasEnvelope = field(default_factory=lambda: GasEnvelope(10.0, 80.0))
    fc_gain_scale: float = 0.5
    fc_gain_ramp_s: float = 30.0

    def phase(self, elapsed_s: float, de_time_s: float, fc_time_s: float) -> str:
        """Return the roast phase for the elapsed time (drying/maillard/development)."""
        if elapsed_s < de_time_s:
            return "drying"
        if elapsed_s < fc_time_s:
            return "maillard"
        return "development"

    def envelope(self, phase: str) -> GasEnvelope:
        return {
            "drying": self.drying,
            "maillard": self.maillard,
            "development": self.development,
        }[phase]

    def clamp_to_envelope(self, value: float, phase: str) -> float:
        """Clamp a burner request to the phase min/max envelope."""
        return self.envelope(phase).clamp(value)

    def gain_scale(self, elapsed_s: float, fc_time_s: float) -> float:
        """Return a 0..1 gain multiplier that ramps down toward fc_gain_scale near FC."""
        if self.fc_gain_ramp_s <= 0 or self.fc_gain_scale >= 1.0:
            return 1.0
        start = fc_time_s - self.fc_gain_ramp_s
        if elapsed_s <= start:
            return 1.0
        if elapsed_s >= fc_time_s:
            return self.fc_gain_scale
        fraction = (elapsed_s - start) / self.fc_gain_ramp_s
        return 1.0 - (1.0 - self.fc_gain_scale) * fraction
