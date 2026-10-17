"""Portable playback-stop rules with no GUI or audio dependencies."""
from __future__ import annotations
from datetime import datetime, timedelta

STOP_MODES = {"duration", "clock", "end_of_playlist"}


def next_occurrence(hour: int, minute: int, after: datetime | None = None) -> datetime:
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Clock time must be in the local 24-hour range")
    after = after or datetime.now()
    target = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= after:
        target += timedelta(days=1)
    return target


def should_stop_at_playlist_end(mode: str, next_index: int, track_count: int) -> bool:
    if mode not in STOP_MODES:
        raise ValueError("Unknown playback stop mode")
    return mode == "end_of_playlist" and next_index >= track_count


def duration_clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"
