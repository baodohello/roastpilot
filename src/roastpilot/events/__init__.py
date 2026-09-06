"""Event types and adapters for roast data sources."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TemperatureReading:
    time_s: float
    bean_temp_c: float
