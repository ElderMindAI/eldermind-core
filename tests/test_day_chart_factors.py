"""Stage A2 of the whole-day mode, checked against a minute-by-minute scan.

Invented days only (no person, no birth data); eldermind-core is public. The
oracle is the natal engines themselves, called once per local minute: the
Western houses (`compute_houses`, `compute_all_planets`,
`attach_houses_to_planets`), the Vedic lagna and nakshatras through the same
calls `compute_vedic_chart` makes, and `compute_bazi`. A boundary the
bisection misses or misplaces shows up as a minute whose value differs.
"""

from __future__ import annotations

from datetime import date, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import pytest

from eldermind_core.core.errors import HouseSystemUnavailableError
from eldermind_core.services.bazi import compute_bazi
from eldermind_core.services.day_variants import (
    ANGLE_STEP_SECONDS,
    SHORT_INTERVAL_SECONDS,
    cut_day,
    day_chart_factors,
)
from eldermind_core.services.decans import decan_index
from eldermind_core.services.ephemeris import (
    _attach_nakshatras,
    _local_to_utc,
    _utc_to_julian_day_ut,
    attach_houses_to_planets,
    compute_all_planets,
    compute_houses,
)

# Invented days and places, each picked for what it exercises:
# the Sun's ingress into Aries in the evening (a body changes sign),
# the autumn clock change in Warsaw (25 hours, a repeated local hour),
# 64 deg N at the June solstice (the Ascendant's decan lasts ~4 minutes,
# the lagna's pada about one), and 69.65 deg N in January (beyond the polar
# circle: no Placidus, the lagna runs backwards and jumps).
INGRESS = (date(2015, 3, 20), "Europe/Warsaw", 52.23, 21.01)
FALL_BACK = (date(2019, 10, 27), "Europe/Warsaw", 52.23, 21.01)
HIGH_NORTH = (date(2011, 6, 21), "Atlantic/Reykjavik", 64.15, -21.94)
POLAR = (date(2012, 1, 10), "Europe/Oslo", 69.65, 18.96)
DAYS = [INGRESS, FALL_BACK, HIGH_NORTH, POLAR]

PILLARS = ("year", "month", "day", "hour")


def _nak(entry: dict) -> dict:
    return {"nakshatra": entry["nakshatra_number"], "name": entry["nakshatra_name"], "pada": entry["pada"]}


def _natal(jd: float, local, latitude: float, longitude: float) -> dict[str, dict]:
    """Every A2 factor as the natal engines give it for one moment."""
    found: dict[str, dict] = {}
    try:
        ascendant, midheaven, houses = compute_houses(jd, latitude, longitude)
    except HouseSystemUnavailableError:
        pass
    else:
        found["ascendant"] = {"sign": ascendant["sign"], "decan": decan_index(ascendant["longitude"]) % 3 + 1}
        found["midheaven"] = {"sign": midheaven["sign"]}
        for planet in attach_houses_to_planets(compute_all_planets(jd), houses):
            found[f"house.{planet['name']}"] = {"house": planet["house_number"]}
    for planet in compute_all_planets(jd):
        found[f"sign.{planet['name']}"] = {"sign": planet["sign"]}

    lagna, _, _ = compute_houses(jd, latitude, longitude, sidereal=True, house_system="whole_sign")
    found["lagna"] = {"sign": lagna["sign"]}
    for entry in _attach_nakshatras(compute_all_planets(jd, sidereal=True), lagna):
        if entry["name"] == "Ascendant":
            found["lagna_nakshatra"] = _nak(entry)
        else:
            found[f"sign_sidereal.{entry['name']}"] = {"sign": entry["sign"]}
            found[f"nakshatra.{entry['name']}"] = _nak(entry)

    bazi = compute_bazi(local.date(), local.time().replace(tzinfo=None))
    found["bazi"] = {name: bazi[f"{name}_pillar"]["hanzi"] for name in PILLARS}
    return found


@lru_cache(maxsize=None)
def _scan(day: date, zone_name: str, latitude: float, longitude: float) -> tuple:
    """(second of day, natal factors) at every whole local minute of the day."""
    zone = ZoneInfo(zone_name)
    start = _local_to_utc(day, time(0, 0), zone_name)
    scan = []
    minute = 0
    while True:
        moment = start + timedelta(minutes=minute)
        local = moment.astimezone(zone)
        if local.date() != day:
            return tuple(scan)
        # Through UTC, not the wall clock: a repeated local hour has no name.
        scan.append((minute * 60, _natal(_utc_to_julian_day_ut(moment), local, latitude, longitude)))
        minute += 1


@lru_cache(maxsize=None)
def _factors(day: date, zone_name: str, latitude: float, longitude: float) -> dict:
    return day_chart_factors(day, zone_name, latitude, longitude)


def _value_at(segments: list[dict], second: int) -> dict:
    for segment in segments:
        if segment["start"]["second_of_day"] <= second < segment["end"]["second_of_day"]:
            return segment["value"]
    raise AssertionError(f"second {second} is outside every segment")


@pytest.mark.parametrize("case", DAYS, ids=["ingress", "fall_back", "high_north", "polar"])
def test_every_minute_matches_the_natal_engines(case: tuple) -> None:
    result = _factors(*case)
    scan = _scan(*case)
    assert set(result["factors"]) == set(scan[0][1])
    for second, natal in scan:
        for factor, expected in natal.items():
            got = _value_at(result["factors"][factor]["segments"], second)
            assert got == expected, (factor, second // 60, got, expected)


@pytest.mark.parametrize("case", DAYS, ids=["ingress", "fall_back", "high_north", "polar"])
def test_segments_cover_the_day_and_changes_are_labelled(case: tuple) -> None:
    result = _factors(*case)
    total = result["day"]["seconds"]
    for factor, data in result["factors"].items():
        segments = data["segments"]
        assert segments[0]["start"]["second_of_day"] == 0
        assert segments[-1]["end"]["second_of_day"] == total
        for before, after in zip(segments, segments[1:]):
            assert before["end"] == after["start"]
            assert before["value"] != after["value"], factor
        for segment in segments:
            assert segment["short"] == (segment["seconds"] < SHORT_INTERVAL_SECONDS)
        if len(segments) == 1:
            assert result["constant"][factor] == segments[0]["value"]
    for change in result["changes"]:
        # The label is the first whole local minute already showing the new value.
        assert change["time"][-2:].isdigit()
        assert change["second_of_day"] > 0


def test_what_each_day_was_picked_for() -> None:
    ingress = _factors(*INGRESS)
    assert [s["value"]["sign"] for s in ingress["factors"]["sign.Sun"]["segments"]] == ["Pisces", "Aries"]
    assert len(ingress["factors"]["ascendant"]["segments"]) == 37  # 36 decans plus the one it started in

    fall_back = _factors(*FALL_BACK)
    assert fall_back["day"]["hours"] == 25
    assert [w["code"] for w in fall_back["warnings"]] == ["CLOCK_CHANGE"]
    hours = [s["value"]["hour"] for s in fall_back["factors"]["bazi"]["segments"]]
    assert len(hours) == 13 and hours[0][1] == "子" and hours[-1][1] == "子"
    # The day pillar changes at 23:00 local (decision of 2026-11-10).
    day_change = [c for c in fall_back["changes"] if any(f["factor"] == "bazi" and f["from"]["day"] != f["to"]["day"] for f in c["factors"])]
    assert [c["time"] for c in day_change] == ["23:00"]

    high = _factors(*HIGH_NORTH)
    shortest = min(s["seconds"] for s in high["factors"]["lagna_nakshatra"]["segments"][1:-1])
    assert shortest < 3 * 60  # a pada of the lagna rises in a couple of minutes at 64 deg

    polar = _factors(*POLAR)
    assert set(polar["unavailable"]) == {"ascendant", "midheaven", "house"}
    assert not any(name.startswith(("house.", "ascendant", "midheaven")) for name in polar["factors"])
    assert "POLAR_LATITUDE" in [w["code"] for w in polar["warnings"]]


def test_angle_grid_is_one_minute() -> None:
    assert ANGLE_STEP_SECONDS == 60


def test_cut_day_cuts_where_any_timeline_changes() -> None:
    def seg(start: int, end: int, value: str) -> dict:
        return {"start": {"second_of_day": start}, "end": {"second_of_day": end}, "value": value}

    cut = cut_day(100, {"a": [seg(0, 40, "x"), seg(40, 100, "y")], "b": [seg(0, 70, "p"), seg(70, 100, "q")]})
    assert [(c["start_second"], c["end_second"], c["values"]) for c in cut] == [
        (0, 40, {"a": "x", "b": "p"}),
        (40, 70, {"a": "y", "b": "p"}),
        (70, 100, {"a": "y", "b": "q"}),
    ]


def test_bad_place_is_refused() -> None:
    with pytest.raises(ValueError):
        day_chart_factors(date(2015, 3, 20), "Europe/Warsaw", 95.0, 21.0)
