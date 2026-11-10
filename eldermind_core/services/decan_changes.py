"""When a body moves into another decan: the moment to the second, shown to the minute.

`decans.py` says which decan a longitude is in. This module adds time: it scans
the ephemeris on a grid finer than the fastest crossing of a 10-degree decan and
bisects every change down to half a second. Retrograde motion is handled like
any other change (the body goes back into the previous decan), so a planet that
crosses a boundary three times around a station yields three changes.

Ascendant and Midheaven need a place (latitude and longitude). They are taken
from Porphyry houses, which are defined at every latitude; the two angles do
not depend on the house system.

All moments are timezone-aware UTC datetimes. Callers convert to local time.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import swisseph as swe

from eldermind_core.core.config import PLANET_IDS
from eldermind_core.services.decans import decan_index, decan_of

ANGLES: tuple[str, ...] = ("Ascendant", "Midheaven")
BODIES: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
)

_SECOND = 1.0 / 86400.0
# Bisection stops below this, so the moment is exact to the second.
_TOLERANCE = 0.5 * _SECOND

# Grid step in days, comfortably shorter than the quickest a body can cross a
# 10-degree decan (Moon about 15 deg/day, Mercury about 2.2 deg/day, the
# Ascendant at high latitudes about 10 deg in a few minutes). Two changes
# inside one step would be missed, so the margin matters more than speed.
_STEP_DAYS: dict[str, float] = {
    "Moon": 1.0 / 24.0,
    "Sun": 0.5,
    "Mercury": 0.25,
    "Venus": 0.25,
    "Mars": 0.5,
    "Jupiter": 1.0,
    "Saturn": 1.0,
    "Uranus": 2.0,
    "Neptune": 2.0,
    "Pluto": 2.0,
    "Ascendant": 1.0 / 1440.0,
    "Midheaven": 1.0 / 1440.0,
}

# How far `next_decan_change` looks before giving up. Long enough for the
# slowest body to leave a decan even with a retrograde loop inside it.
_HORIZON_DAYS: dict[str, float] = {
    "Moon": 5.0,
    "Sun": 15.0,
    "Mercury": 400.0,
    "Venus": 400.0,
    "Mars": 800.0,
    "Jupiter": 1500.0,
    "Saturn": 2500.0,
    "Uranus": 6000.0,
    "Neptune": 9000.0,
    "Pluto": 9000.0,
    "Ascendant": 1.0,
    "Midheaven": 1.0,
}


def _require_aware(moment: datetime, name: str) -> None:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware, got naive {moment!r}")


def _check_body(body: str, latitude: float | None, longitude: float | None) -> None:
    if body not in _STEP_DAYS:
        raise ValueError(f"unknown body {body!r}; expected one of {sorted(_STEP_DAYS)}")
    if body in ANGLES and (latitude is None or longitude is None):
        raise ValueError(f"{body} needs latitude and longitude")


def julian_day(moment: datetime) -> float:
    """Julian Day (UT) of an aware datetime."""
    _require_aware(moment, "moment")
    utc = moment.astimezone(timezone.utc)
    hours = utc.hour + utc.minute / 60.0 + utc.second / 3600.0 + utc.microsecond / 3.6e9
    return swe.julday(utc.year, utc.month, utc.day, hours)


def moment_of(jd_ut: float) -> datetime:
    """UTC datetime of a Julian Day, rounded to the nearest second."""
    year, month, day, hours = swe.revjul(jd_ut)
    seconds = round(hours * 3600.0)
    return datetime(year, month, day, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def to_minute(moment: datetime) -> datetime:
    """Nearest whole minute (30 s rounds up), as shown on screen."""
    return (moment + timedelta(seconds=30)).replace(second=0, microsecond=0)


def body_longitude(
    body: str,
    jd_ut: float,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> float:
    """Tropical longitude of a planet or an angle, in [0, 360)."""
    if body in ANGLES:
        _, ascmc = swe.houses_ex(jd_ut, latitude, longitude, b"O", 0)
        return float(ascmc[0 if body == "Ascendant" else 1]) % 360.0
    result, _ = swe.calc_ut(jd_ut, PLANET_IDS[body], 0)
    return float(result[0]) % 360.0


def body_decan(
    body: str,
    moment: datetime,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict:
    """`decan_of` for a body at a moment, with the body's name added."""
    _check_body(body, latitude, longitude)
    lon = body_longitude(body, julian_day(moment), latitude=latitude, longitude=longitude)
    return {"name": body, **decan_of(lon)}


def _change(body: str, jd_before: float, jd_after: float, index_of) -> dict:
    """Bisect [jd_before, jd_after], where the index differs at the two ends."""
    before = index_of(jd_before)
    a, b = jd_before, jd_after
    while b - a > _TOLERANCE:
        middle = (a + b) / 2.0
        if index_of(middle) == before:
            a = middle
        else:
            b = middle
    exact = moment_of(b)
    after = index_of(julian_day(exact))
    if after == before:
        # Rounding to the second landed on the old side: the next second is new.
        exact += timedelta(seconds=1)
        after = index_of(julian_day(exact))
    return {
        "body": body,
        "from_index": before,
        "to_index": after,
        "direction": "forward" if (after - before) % 36 == 1 else "backward",
        "moment_exact": exact,
        "moment": to_minute(exact),
    }


def decan_changes(
    body: str,
    start: datetime,
    end: datetime,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
) -> list[dict]:
    """Every decan change of `body` in (start, end], in time order.

    Each change: `from_index`, `to_index` (0-35), `direction` (`forward` or
    `backward` for retrograde), `moment_exact` (UTC, to the second, the first
    second in the new decan) and `moment` (the same rounded to the minute).
    """
    _check_body(body, latitude, longitude)
    _require_aware(start, "start")
    _require_aware(end, "end")
    jd_start, jd_end = julian_day(start), julian_day(end)
    if jd_end <= jd_start:
        return []

    def index_of(jd: float) -> int:
        return decan_index(body_longitude(body, jd, latitude=latitude, longitude=longitude))

    step = _STEP_DAYS[body]
    changes: list[dict] = []
    jd, current = jd_start, index_of(jd_start)
    while jd < jd_end:
        nxt = min(jd + step, jd_end)
        index = index_of(nxt)
        if index != current:
            changes.append(_change(body, jd, nxt, index_of))
            current = index
        jd = nxt
    return changes


def next_decan_change(
    body: str,
    after: datetime,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    horizon_days: float | None = None,
) -> dict | None:
    """The first decan change of `body` after `after`, or None within the horizon.

    Same shape as one entry of `decan_changes`. The horizon defaults to a span
    in which the body always leaves its decan, so None means a caller-supplied
    horizon was too short.
    """
    _check_body(body, latitude, longitude)
    _require_aware(after, "after")
    horizon = horizon_days if horizon_days is not None else _HORIZON_DAYS[body]
    # Searched in chunks, so a slow body does not pay for the whole horizon.
    chunk = max(_STEP_DAYS[body] * 200, 1.0 / 24.0)
    start, limit = after, after + timedelta(days=horizon)
    while start < limit:
        end = min(start + timedelta(days=chunk), limit)
        found = decan_changes(body, start, end, latitude=latitude, longitude=longitude)
        if found:
            return found[0]
        start = end
    return None


__all__ = [
    "ANGLES",
    "BODIES",
    "body_decan",
    "body_longitude",
    "decan_changes",
    "julian_day",
    "moment_of",
    "next_decan_change",
    "to_minute",
]
