from __future__ import annotations


def parse_mmss(value: str) -> float:
    value = value.strip()
    if ":" not in value:
        raise ValueError(f"Invalid time '{value}'. Use MM:SS.")
    minutes, seconds = value.split(":", 1)
    try:
        minutes, seconds = float(minutes), float(seconds)
    except ValueError as error:
        raise ValueError(f"Invalid time '{value}'. Use MM:SS.") from error
    if minutes < 0 or not 0 <= seconds < 60:
        raise ValueError("Seconds must be between 0 and 59; time cannot be negative.")
    return minutes * 60 + seconds
