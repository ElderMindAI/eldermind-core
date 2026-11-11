"""Every result one local day can give when the birth time is unknown (stage A1).

Without a birth time the product used to compute 12:00 and say so. This module
answers the better question: over the whole local day of birth, which results
are possible, from when to when, and what changes at each boundary.

Stage A1 covers what Human Design and Animal Design read from the hour: the
gate of every body on both sides (the Moon above all), the lines that matter
(the Sun's for the profile, the Moon's), and everything derived from them
(type, authority, definition, profile, centers, channels; for animals the 15
mammalian gates and their groups and portals). The angles, houses, the Moon's
sign and nakshatra, the lagna and the BaZi hour pillar are stage A2.

How it works. Every tracked value is a function of one body's longitude at
one moment (the birth moment for the Personality side, the Design moment for
the Design side). The day is sampled every `step_minutes`; where a body's value
differs between two samples, that one body is bisected to the first whole
second of the new value. A full chart is never recomputed inside a bisection,
which is what makes a day take well under a second instead of the ~14 s of a
1440-minute scan. The grid step must stay shorter than the quickest a tracked
value can change twice (the Moon's line, about 1.7 h), so a change and its
reversal cannot hide inside one step.

The local day runs from local midnight to the next local midnight in the
historical zone, so a clock change gives 23 or 25 hours. Times are shown as
the first whole local minute with the new result: a birth recorded at that
minute gets it, one recorded a minute earlier does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import swisseph as swe

from eldermind_core import ENGINE_VERSION
from eldermind_core.core.animal_design_constants import ANIMAL_GATES
from eldermind_core.core.hd_constants import HD_BODY_IDS
from eldermind_core.services.animal_design import (
    compute_animal_design_mechanics,
    find_animal_design_julian_day,
)
from eldermind_core.services.ephemeris import (
    _assert_valid_timezone,
    _local_to_utc,
    _utc_to_julian_day_ut,
)
from eldermind_core.services.human_design import (
    compute_hd_mechanics,
    find_design_julian_day,
    longitude_to_gate_line,
)

MODES: tuple[str, ...] = ("animal", "human")
SIDES: tuple[str, ...] = ("Personality", "Design")

#: Intervals shorter than this are marked `short`: shown on the time axis,
#: never described on their own (owner's decision, 2026-11-11).
SHORT_INTERVAL_SECONDS = 5 * 60

#: Grid step. The Moon's line (0.9375 degrees) is the fastest tracked value and
#: lasts about 1.7 h; 10 minutes leaves a wide margin and costs ~150 samples.
DEFAULT_STEP_MINUTES = 10

#: Systems computed from the date alone: the hour never changes them.
TIME_INDEPENDENT_SYSTEMS: dict[str, tuple[str, ...]] = {
    "animal": (),
    "human": ("numerology", "matrix"),
}

#: Bodies whose line is tracked besides the gate. The profile reads the Sun's
#: line (the Earth sits exactly 32 gates away, so its line is the Sun's).
_LINE_BODIES: dict[str, frozenset[str]] = {
    "animal": frozenset(),
    "human": frozenset({"Sun", "Earth", "Moon"}),
}

#: Human chart fields that define a variant. Moon lines and gates outside the
#: chart change more often and are listed as changes without splitting it.
_HUMAN_VARIANT_FIELDS: tuple[str, ...] = (
    "type",
    "authority",
    "definition",
    "profile",
    "defined_centers",
    "channels",
)

_OFFSET = {"Earth": 180.0, "SouthNode": 180.0}

Key = tuple[str, str]  # (side, body)


@dataclass(frozen=True)
class _Mode:
    name: str
    design_jd: Callable[[float], float]


_MODES = {
    "animal": _Mode("animal", find_animal_design_julian_day),
    "human": _Mode("human", find_design_julian_day),
}


def _longitude(jd_ut: float, planet_id: int) -> float:
    """The longitude `compute_planet_position` returns, without its speed calls.

    That function asks for the position without speed flags, so it always
    falls back to two more ephemeris calls for a derivative nobody reads here.
    Same rounding to six decimals, so a boundary falls on the same second as in
    a chart computed by the natal engines at that moment.
    """
    result, err = swe.calc_ut(jd_ut, planet_id, 0)
    if err and not result:
        raise RuntimeError(f"Ephemeris calculation failed for body {planet_id}: {err}")
    return round(float(result[0]) % 360.0, 6)


def _activation(jd_ut: float, body: str, longitude: float | None = None) -> tuple[int, int]:
    if longitude is None:
        longitude = _longitude(jd_ut, HD_BODY_IDS[body])
    found = longitude_to_gate_line((longitude + _OFFSET.get(body, 0.0)) % 360.0)
    return int(found["gate"]), int(found["line"])


class _Day:
    """One local day: seconds from local midnight to Julian Days, with caches."""

    def __init__(self, day: date, timezone_name: str, mode: str) -> None:
        self.zone = ZoneInfo(timezone_name)
        self.mode = _MODES[mode]
        self.lines = _LINE_BODIES[mode]
        self.start_utc = _local_to_utc(day, time(0, 0), timezone_name)
        self.end_utc = _local_to_utc(day + timedelta(days=1), time(0, 0), timezone_name)
        self.seconds = int((self.end_utc - self.start_utc).total_seconds())
        if self.seconds <= 0:
            raise ValueError(f"{day.isoformat()} does not exist in {timezone_name}")
        self._jd: dict[int, tuple[float, float]] = {}

    def utc(self, second: int) -> datetime:
        return self.start_utc + timedelta(seconds=second)

    def local(self, second: int) -> datetime:
        return self.utc(second).astimezone(self.zone)

    def julian_days(self, second: int) -> tuple[float, float]:
        """(birth, design) Julian Days UT for a moment `second` after midnight."""
        found = self._jd.get(second)
        if found is None:
            jd = _utc_to_julian_day_ut(self.utc(second))
            found = (jd, self.mode.design_jd(jd))
            self._jd[second] = found
        return found

    def value(self, second: int, key: Key) -> tuple[int, ...]:
        side, body = key
        jd_birth, jd_design = self.julian_days(second)
        gate, line = _activation(jd_birth if side == "Personality" else jd_design, body)
        return (gate, line) if body in self.lines else (gate,)

    def state(self, second: int) -> dict[Key, tuple[int, ...]]:
        found: dict[Key, tuple[int, ...]] = {}
        for side, jd in zip(SIDES, self.julian_days(second)):
            # Sun and Earth, North and South Node: one ephemeris call per pair.
            longitudes = {pid: _longitude(jd, pid) for pid in set(HD_BODY_IDS.values())}
            for body, pid in HD_BODY_IDS.items():
                gate, line = _activation(jd, body, longitudes[pid])
                found[(side, body)] = (gate, line) if body in self.lines else (gate,)
        return found


def _first_change(day: _Day, key: Key, low: int, high: int) -> int:
    """First whole second in (low, high] whose value differs from `low`'s."""
    before = day.value(low, key)
    while high - low > 1:
        middle = (low + high) // 2
        if day.value(middle, key) == before:
            low = middle
        else:
            high = middle
    return high


def _activations(state: dict[Key, tuple[int, ...]], side: str) -> list[dict]:
    rows = []
    for body in HD_BODY_IDS:
        value = state[(side, body)]
        rows.append({"name": body, "gate": value[0], "line": value[1] if len(value) > 1 else 1})
    return rows


def _result(mode: str, state: dict[Key, tuple[int, ...]]) -> dict:
    """The chart a moment gives, reduced to what defines a variant."""
    personality, design = _activations(state, "Personality"), _activations(state, "Design")
    if mode == "animal":
        mechanics = compute_animal_design_mechanics(
            [a for a in personality if a["gate"] in ANIMAL_GATES],
            [a for a in design if a["gate"] in ANIMAL_GATES],
        )
        mechanics["channels"] = [channel["id"] for channel in mechanics["channels"]]
        return mechanics
    mechanics = compute_hd_mechanics(personality, design)
    result = {field: mechanics[field] for field in _HUMAN_VARIANT_FIELDS}
    result["channels"] = sorted(channel["id"] for channel in mechanics["channels"])
    return result


def _variant_key(mode: str, result: dict) -> tuple:
    if mode == "animal":
        return tuple(result["activated_gates"])
    return tuple(
        tuple(result[field]) if isinstance(result[field], list) else result[field]
        for field in _HUMAN_VARIANT_FIELDS
    )


def _counts(mode: str, key: Key, before: tuple[int, ...], after: tuple[int, ...]) -> bool:
    """Whether an activation change can matter for the result at all."""
    if mode == "animal":
        return before[0] in ANIMAL_GATES or after[0] in ANIMAL_GATES
    return True


def _minute_label(moment: datetime) -> str:
    """First whole local minute at or after `moment`, as HH:MM."""
    if moment.second or moment.microsecond:
        moment = moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return moment.strftime("%H:%M")


def _stamp(day: _Day, second: int) -> dict:
    local = day.local(second)
    return {
        "time": _minute_label(local),
        "exact": local.isoformat(),
        "utc": day.utc(second).astimezone(timezone.utc).isoformat(),
        "second_of_day": second,
    }


def _warnings(day: _Day, timezone_name: str) -> list[dict]:
    notes: list[dict] = []
    hours = day.seconds / 3600.0
    if day.seconds != 86400:
        notes.append(
            {
                "code": "CLOCK_CHANGE",
                "message": (
                    f"The local day in {timezone_name} has {hours:g} hours because the "
                    "clocks changed; times inside the repeated or skipped hour carry "
                    "their UTC offset."
                ),
            }
        )
    for second in (0, day.seconds - 1):
        local = day.local(second)
        offset = local.utcoffset() or timedelta(0)
        if local.tzname() == "LMT" or offset.total_seconds() % 900:
            notes.append(
                {
                    "code": "LOCAL_MEAN_TIME",
                    "message": (
                        f"{timezone_name} on this date used local mean time "
                        f"(UTC{_offset_text(offset)}), before standard time zones. A "
                        "time recorded then followed the clock of the actual town, so "
                        "every minute here is approximate."
                    ),
                }
            )
            break
    return notes


def _offset_text(offset: timedelta) -> str:
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    text = f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"
    return text + (f":{total % 60:02d}" if total % 60 else "")


def day_variants(
    day: date,
    timezone_name: str,
    *,
    mode: str = "animal",
    step_minutes: int = DEFAULT_STEP_MINUTES,
) -> dict:
    """Every Human Design or Animal Design result possible on one local day.

    Args:
        day: The local date of birth.
        timezone_name: IANA zone of the birth place (its history is used).
        mode: ``"animal"`` (15 mammalian gates, Moon-based Design moment) or
            ``"human"`` (Human Design, Sun-based Design moment).
        step_minutes: Sampling grid; changes are then bisected to the second.

    Returns:
        A JSON-ready dict:

        * ``day``: local start and end, length in seconds and hours.
        * ``intervals``: the day cut where the result changes, each with
          ``start``/``end`` stamps, ``seconds``, ``short`` (under 5 minutes)
          and the ``variant`` it shows.
        * ``variants``: each distinct result once, with its ``result``, the
          ``intervals`` it occupies and its total ``seconds``. A result can
          come back later in the day (a gate leaves and returns).
        * ``changes``: every moment something tracked changes, with the
          ``activations`` that moved (side, body, from, to, ``counts``) and
          ``new_interval`` when the result itself changed.
        * ``constant``: result fields equal across the whole day, and for
          animals ``gates_always``/``gates_sometimes``.
        * ``time_independent_systems`` and ``warnings`` (clock change, local
          mean time before standard zones).
    """
    if mode not in _MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    if step_minutes < 1:
        raise ValueError("step_minutes must be at least 1")
    _assert_valid_timezone(timezone_name)
    ctx = _Day(day, timezone_name, mode)
    step = step_minutes * 60
    last = ctx.seconds - 1  # the day is [start, end): its last second

    grid = list(range(0, last, step)) + [last]
    samples = {second: ctx.state(second) for second in grid}

    # Elementary changes, per body, bisected to the first whole second.
    elementary: list[tuple[int, Key, tuple[int, ...], tuple[int, ...]]] = []
    for low, high in zip(grid, grid[1:]):
        for key, value in samples[low].items():
            if samples[high][key] == value:
                continue
            cursor, current = low, value
            while current != samples[high][key]:
                moment = _first_change(ctx, key, cursor, high)
                new = ctx.value(moment, key)
                elementary.append((moment, key, current, new))
                cursor, current = moment, new
    elementary.sort(key=lambda item: (item[0], SIDES.index(item[1][0]), list(HD_BODY_IDS).index(item[1][1])))

    # Replay the changes from midnight, cutting an interval wherever the result moves.
    state = dict(samples[0])
    result = _result(mode, state)
    variants: list[dict] = []
    index_of: dict[tuple, int] = {}

    def variant_id(found: dict) -> int:
        key = _variant_key(mode, found)
        if key not in index_of:
            index_of[key] = len(variants)
            variants.append({"id": len(variants), "result": found, "intervals": [], "seconds": 0})
        return index_of[key]

    intervals: list[dict] = [{"start_second": 0, "variant": variant_id(result)}]
    changes: list[dict] = []
    position = 0
    while position < len(elementary):
        moment = elementary[position][0]
        moved = []
        while position < len(elementary) and elementary[position][0] == moment:
            _, key, before, after = elementary[position]
            state[key] = after
            moved.append(
                {
                    "side": key[0],
                    "body": key[1],
                    "from": _value_dict(before),
                    "to": _value_dict(after),
                    "counts": _counts(mode, key, before, after),
                }
            )
            position += 1
        found = _result(mode, state)
        vid = variant_id(found)
        change = {**_stamp(ctx, moment), "activations": moved, "new_interval": None}
        if vid != intervals[-1]["variant"]:
            previous = variants[intervals[-1]["variant"]]["result"]
            change["new_interval"] = len(intervals)
            change["fields"] = {
                field: {"from": previous[field], "to": found[field]}
                for field in found
                if found[field] != previous[field]
            }
            intervals.append({"start_second": moment, "variant": vid})
        changes.append(change)

    out_intervals = []
    for number, interval in enumerate(intervals):
        start = interval["start_second"]
        end = intervals[number + 1]["start_second"] if number + 1 < len(intervals) else ctx.seconds
        seconds = end - start
        variants[interval["variant"]]["intervals"].append(number)
        variants[interval["variant"]]["seconds"] += seconds
        out_intervals.append(
            {
                "index": number,
                "variant": interval["variant"],
                "start": _stamp(ctx, start),
                "end": _stamp(ctx, end),
                "seconds": seconds,
                "short": seconds < SHORT_INTERVAL_SECONDS,
            }
        )

    return {
        "mode": mode,
        "date": day.isoformat(),
        "timezone": timezone_name,
        "engine_version": ENGINE_VERSION,
        "day": {
            "start": ctx.local(0).isoformat(),
            "end": ctx.end_utc.astimezone(ctx.zone).isoformat(),
            "seconds": ctx.seconds,
            "hours": ctx.seconds / 3600.0,
        },
        "intervals": out_intervals,
        "variants": variants,
        "changes": changes,
        "constant": _constant(mode, [v["result"] for v in variants]),
        "time_independent_systems": list(TIME_INDEPENDENT_SYSTEMS[mode]),
        "warnings": _warnings(ctx, timezone_name),
    }


def _value_dict(value: tuple[int, ...]) -> dict:
    return {"gate": value[0], "line": value[1]} if len(value) > 1 else {"gate": value[0]}


def _constant(mode: str, results: list[dict]) -> dict:
    first = results[0]
    fields = ("type", "authority", "definition", "defined_centers", "channels")
    if mode == "human":
        fields = _HUMAN_VARIANT_FIELDS
    constant = {field: first[field] for field in fields if all(r[field] == first[field] for r in results)}
    if mode == "animal":
        sets = [set(r["activated_gates"]) for r in results]
        always = set.intersection(*sets)
        constant["gates_always"] = sorted(always)
        constant["gates_sometimes"] = sorted(set.union(*sets) - always)
    return constant


__all__ = [
    "DEFAULT_STEP_MINUTES",
    "MODES",
    "SHORT_INTERVAL_SECONDS",
    "TIME_INDEPENDENT_SYSTEMS",
    "day_variants",
]
