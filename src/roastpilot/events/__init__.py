"""Event types and adapters for roast data sources."""

from dataclasses import dataclass
from enum import Enum


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAULT = "fault"


@dataclass(frozen=True)
class TemperatureReading:
    time_s: float
    bean_temp_c: float
    exhaust_temp_c: float | None = None


@dataclass(frozen=True)
class BurnerCommand:
    percent: float
    source: str = "manual"  # "manual" or "auto"
    time_s: float | None = None


__all__ = ["ConnectionState", "TemperatureReading", "BurnerCommand"]
