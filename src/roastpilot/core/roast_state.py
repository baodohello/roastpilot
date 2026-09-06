from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ControlMode(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"


@dataclass
class RoastState:
    running: bool = False
    mode: ControlMode = ControlMode.MANUAL
    elapsed_s: float = 0.0
    bean_temp_c: float = 25.0
    ror_c_per_min: float | None = None
    target_ror_c_per_min: float | None = None
    burner_percent: float = 0.0
    warning: str | None = None
    history: list[tuple[float, float, float | None]] = field(default_factory=list)

    def reset(self, ambient_temp_c: float = 25.0) -> None:
        self.running = False
        self.elapsed_s = 0.0
        self.bean_temp_c = ambient_temp_c
        self.ror_c_per_min = None
        self.target_ror_c_per_min = None
        self.burner_percent = 0.0
        self.warning = None
        self.history.clear()
