"""Every result of one local day (stage A1), checked against a minute-by-minute scan.

Invented days only (no person, no birth data); eldermind-core is public. The
oracle is the natal engines themselves, called once per local minute through
their public entry points, so a boundary the bisection misses or misplaces
shows up as a minute whose result differs.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import pytest

from eldermind_core.services.animal_design import compute_animal_design
from eldermind_core.services.day_variants import (
    SHORT_INTERVAL_SECONDS,
    TIME_INDEPENDENT_SYSTEMS,
    day_variants,
)
from eldermind_core.services.ephemeris import _local_to_utc, _utc_to_julian_day_ut
from eldermind_core.services.human_design import compute_human_design

# Invented days, picked for having something to find: the animal day changes
# Type (Reflector and Generator), the human one has six intervals, and the
# third is the spring clock change in Warsaw (23 hours, five intervals).
ANIMAL_DAY = (date(2004, 2, 4), "Europe/Warsaw")
HUMAN_DAY = (date(1983, 8, 11), "America/Chicago")
SPRING_FORWARD = (date(2019, 3, 31), "Europe/Warsaw")
FALL_BACK = (date(2019, 10, 27), "Europe/Warsaw")


def _animal_key(mechanics: dict) -> tuple:
    return tuple(mechanics["activated_gates"])


def _human_key(mechanics: dict) -> tuple:
    channels = mechanics["channels"]
    ids = sorted(c["id"] if isinstance(c, dict) else c for c in channels)
    return (
        mechanics["type"],
        mechanics["authority"],
        mechanics["definition"],
        mechanics["profile"],
        tuple(sorted(mechanics["defined_centers"])),
        tuple(ids),
    )


def _minute_scan(day: date, zone_name: str, mode: str) -> list[tuple[int, tuple]]:
    """(second of day, result key) at every whole local minute of the day."""
    zone = ZoneInfo(zone_name)
    start = _local_to_utc(day, time(0, 0), zone_name)
    scan = []
    minute = 0
    while True:
        moment = start + timedelta(minutes=minute)
        if moment.astimezone(zone).date() != day:
            return scan
        # Through UTC, not the wall clock: a repeated local hour has no name.
        jd = _utc_to_julian_day_ut(moment)
        if mode == "animal":
            key = _animal_key(compute_animal_design(jd)["mechanics"])
        else:
            key = _human_key(compute_human_design(jd)["mechanics"])
        scan.append((minute * 60, key))
        minute += 1


@lru_cache(maxsize=None)
def _variants(day: date, zone_name: str, mode: str) -> dict:
    return day_variants(day, zone_name, mode=mode)


def _key_at(result: dict, second: int) -> tuple:
    for interval in result["intervals"]:
        if interval["start"]["second_of_day"] <= second < interval["end"]["second_of_day"]:
            found = result["variants"][interval["variant"]]["result"]
            return _animal_key(found) if result["mode"] == "animal" else _human_key(found)
    raise AssertionError(f"second {second} is in no interval")


@pytest.mark.parametrize(
    ("day", "mode"),
    [(ANIMAL_DAY, "animal"), (HUMAN_DAY, "human"), (SPRING_FORWARD, "animal")],
    ids=["animal", "human", "spring-forward"],
)
def test_every_minute_matches_the_natal_engine(day: tuple[date, str], mode: str) -> None:
    result = _variants(*day, mode)
    scan = _minute_scan(*day, mode)
    assert len(scan) * 60 == result["day"]["seconds"]
    assert len(result["intervals"]) >= 4, "an invented day with nothing to find tests nothing"
    wrong = [
        (second // 60, key, _key_at(result, second))
        for second, key in scan
        if _key_at(result, second) != key
    ]
    assert wrong == []
    # The scan must not see more changes than the intervals list, either.
    scan_starts = [scan[0][0]] + [s for (s, k), (_, p) in zip(scan[1:], scan) if k != p]
    interval_starts = [-(-i["start"]["second_of_day"] // 60) * 60 for i in result["intervals"]]
    assert scan_starts == interval_starts


def test_intervals_cover_the_day_without_gaps() -> None:
    for day, mode in ((ANIMAL_DAY, "animal"), (HUMAN_DAY, "human")):
        result = _variants(*day, mode)
        intervals = result["intervals"]
        assert intervals[0]["start"]["second_of_day"] == 0
        assert intervals[-1]["end"]["second_of_day"] == result["day"]["seconds"]
        for left, right in zip(intervals, intervals[1:]):
            assert left["end"] == right["start"]
            assert left["variant"] != right["variant"]
        assert sum(i["seconds"] for i in intervals) == result["day"]["seconds"]
        assert sum(v["seconds"] for v in result["variants"]) == result["day"]["seconds"]
        for interval in intervals:
            assert interval["short"] == (interval["seconds"] < SHORT_INTERVAL_SECONDS)
            assert interval["index"] in result["variants"][interval["variant"]]["intervals"]


def test_changes_explain_every_new_interval() -> None:
    result = _variants(*HUMAN_DAY, "human")
    opening = [c for c in result["changes"] if c["new_interval"] is not None]
    assert [c["new_interval"] for c in opening] == list(range(1, len(result["intervals"])))
    for change in opening:
        interval = result["intervals"][change["new_interval"]]
        assert change["second_of_day"] == interval["start"]["second_of_day"]
        assert change["fields"], "a new interval must name what changed"
        assert change["activations"], "and which body moved"
    # Moon lines move every ~1.7 h on both sides: far more changes than intervals.
    moon = [a for c in result["changes"] for a in c["activations"] if a["body"] == "Moon"]
    assert len(moon) >= 20


def test_times_are_the_first_whole_minute_of_the_new_result() -> None:
    result = _variants(*ANIMAL_DAY, "animal")
    zone = ZoneInfo(ANIMAL_DAY[1])
    for change in result["changes"]:
        exact = datetime.fromisoformat(change["exact"])
        shown = datetime.combine(ANIMAL_DAY[0], time.fromisoformat(change["time"]), zone)
        assert timedelta(0) <= shown - exact < timedelta(minutes=1)


def test_constant_fields_hold_in_every_variant() -> None:
    result = _variants(*ANIMAL_DAY, "animal")
    constant = result["constant"]
    assert "type" not in constant  # Reflector and Generator on this day
    assert {v["result"]["type"] for v in result["variants"]} == {"Reflector", "Generator"}
    for variant in result["variants"]:
        for field in ("type", "authority", "definition", "defined_centers", "channels"):
            if field in constant:
                assert variant["result"][field] == constant[field]
        assert set(constant["gates_always"]) <= set(variant["result"]["activated_gates"])
    union = set().union(*(v["result"]["activated_gates"] for v in result["variants"]))
    assert set(constant["gates_always"]) | set(constant["gates_sometimes"]) == union


def test_clock_change_days_have_23_and_25_hours() -> None:
    spring = _variants(*SPRING_FORWARD, "animal")
    fall = day_variants(*FALL_BACK, mode="animal")
    assert spring["day"]["seconds"] == 23 * 3600
    assert fall["day"]["seconds"] == 25 * 3600
    for result in (spring, fall):
        assert [w["code"] for w in result["warnings"]] == ["CLOCK_CHANGE"]
    assert [w["code"] for w in _variants(*ANIMAL_DAY, "animal")["warnings"]] == []


def test_local_mean_time_before_standard_zones_is_flagged() -> None:
    old = day_variants(date(1890, 5, 1), "Europe/Warsaw", mode="animal")
    assert "LOCAL_MEAN_TIME" in [w["code"] for w in old["warnings"]]


def test_time_independent_systems() -> None:
    assert _variants(*HUMAN_DAY, "human")["time_independent_systems"] == ["numerology", "matrix"]
    assert _variants(*ANIMAL_DAY, "animal")["time_independent_systems"] == []
    assert TIME_INDEPENDENT_SYSTEMS["animal"] == ()


def test_bad_arguments() -> None:
    with pytest.raises(ValueError):
        day_variants(*ANIMAL_DAY, mode="plant")
    with pytest.raises(ValueError):
        day_variants(*ANIMAL_DAY, step_minutes=0)
    # Samoa skipped this whole day when it crossed the date line.
    with pytest.raises(ValueError):
        day_variants(date(2011, 12, 30), "Pacific/Apia")
