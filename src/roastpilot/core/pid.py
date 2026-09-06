from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PIDController:
    """A bounded PID controller with derivative-on-measurement and anti-windup."""

    kp: float = 1.0
    ki: float = 0.1
    kd: float = 0.0
    output_min: float = 0.0
    output_max: float = 100.0
    integral: float = 0.0
    previous_measurement: float | None = None

    def reset(self) -> None:
        self.integral = 0.0
        self.previous_measurement = None

    def update(self, setpoint: float, measurement: float, dt_s: float) -> float:
        if dt_s <= 0:
            raise ValueError("dt_s must be positive")
        error = setpoint - measurement
        derivative = 0.0
        if self.previous_measurement is not None:
            derivative = -(measurement - self.previous_measurement) / dt_s
        candidate_integral = self.integral + error * dt_s
        candidate = self.kp * error + self.ki * candidate_integral + self.kd * derivative
        output = max(self.output_min, min(self.output_max, candidate))
        if output == candidate or (output == self.output_max and error < 0) or (output == self.output_min and error > 0):
            self.integral = candidate_integral
        self.previous_measurement = measurement
        return output
