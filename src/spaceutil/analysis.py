"""Occupancy math for rooms and zones from badge visit records."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

FMT = "%Y-%m-%d %H:%M"


@dataclass(frozen=True)
class Visit:
    """One person in one space, from badge-in to badge-out."""

    badge: str
    space: str
    entry: datetime
    exit: datetime

    @property
    def hours(self) -> float:
        return (self.exit - self.entry).total_seconds() / 3600


def _parse(value: str, line: int) -> datetime:
    try:
        return datetime.strptime(value.strip(), FMT)
    except ValueError:
        raise ValueError(f"line {line}: bad time '{value}', expected YYYY-MM-DD HH:MM") from None


def load_spaces(path: str | Path) -> dict[str, int]:
    """Read a CSV with columns space,capacity."""
    spaces: dict[str, int] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            try:
                cap = int(row["capacity"])
                name = row["space"].strip()
            except (KeyError, ValueError, AttributeError):
                raise ValueError(f"{path} line {n}: need space and a whole-number capacity") from None
            if cap <= 0 or not name:
                raise ValueError(f"{path} line {n}: capacity must be above zero")
            spaces[name] = cap
    return spaces


def load_visits(path: str | Path, spaces: dict[str, int]) -> list[Visit]:
    """Read a CSV with columns badge,space,entry,exit and check it against the space list."""
    visits: list[Visit] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            try:
                space = row["space"].strip()
                entry = _parse(row["entry"], n)
                leave = _parse(row["exit"], n)
                badge = row["badge"].strip()
            except (KeyError, AttributeError):
                raise ValueError(f"{path} line {n}: need badge,space,entry,exit") from None
            if space not in spaces:
                raise ValueError(f"{path} line {n}: unknown space '{space}'")
            if leave <= entry:
                raise ValueError(f"{path} line {n}: exit is not after entry")
            visits.append(Visit(badge, space, entry, leave))
    return visits


def peak_occupancy(visits: list[Visit]) -> int:
    """Highest number of people inside at the same moment.

    A badge-out at the same minute as a badge-in frees the seat first.
    """
    points = sorted([(v.entry, 1) for v in visits] + [(v.exit, -1) for v in visits])
    now = best = 0
    for _, step in points:
        now += step
        best = max(best, now)
    return best


def hourly_profile(visits: list[Visit], first: int = 8, last: int = 17) -> dict[int, float]:
    """Average headcount for each clock hour from `first` up to but not including `last`, across the days seen."""
    days = {v.entry.date() for v in visits}
    if not days:
        return {h: 0.0 for h in range(first, last)}
    profile: dict[int, float] = {}
    for hour in range(first, last):
        person_hours = 0.0
        for v in visits:
            start = v.entry.replace(hour=hour, minute=0)
            end = start + timedelta(hours=1)
            overlap = (min(v.exit, end) - max(v.entry, start)).total_seconds() / 3600
            person_hours += max(0.0, overlap)
        profile[hour] = round(person_hours / len(days), 1)
    return profile


def space_stats(visits: list[Visit], spaces: dict[str, int], day_hours: float = 9.0) -> list[dict]:
    """One row per space: visit count, peak, capacity and utilization percent.

    Utilization is person-hours used divided by capacity times day_hours times the number of days in the data.
    """
    days = {v.entry.date() for v in visits}
    rows = []
    for name, cap in spaces.items():
        mine = [v for v in visits if v.space == name]
        used = sum(v.hours for v in mine)
        available = cap * day_hours * len(days)
        util = 100 * used / available if available else 0.0
        rows.append({
            "space": name, "capacity": cap, "visits": len(mine),
            "peak": peak_occupancy(mine), "utilization": round(util, 1),
        })
    return rows


def flag(row: dict, low: float) -> str:
    """OVER when the peak passed capacity, UNDER when utilization is below `low` percent, else empty."""
    if row["peak"] > row["capacity"]:
        return "OVER"
    if row["utilization"] < low:
        return "UNDER"
    return ""
