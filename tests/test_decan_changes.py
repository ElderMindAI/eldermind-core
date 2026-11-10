"""Decan changes in time: values, not shapes.

Sky moments only (no person, no birth data); eldermind-core is public.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from eldermind_core.services.decan_changes import (
    body_decan,
    body_longitude,
    decan_changes,
    julian_day,
    moment_of,
    next_decan_change,
    to_minute,
)
from eldermind_core.services.decans import decan_index

WARSAW = ZoneInfo("Europe/Warsaw")
NOON = datetime(2026, 11, 10, 12, 0, tzinfo=WARSAW)
# An invented place at mid-latitude (roughly Krakow).
LAT, LON = 50.06, 19.94


def _index(body: str, moment: datetime, **place: float) -> int:
    return decan_index(body_longitude(body, julian_day(moment), **place))


def test_sun_change_after_a_noon_is_the_minute_from_the_spec() -> None:
    change = next_decan_change("Sun", NOON)
    assert (change["from_index"], change["to_index"]) == (22, 23)
    assert change["direction"] == "forward"
    assert change["moment_exact"] == datetime(2026, 11, 12, 9, 16, 53, tzinfo=timezone.utc)
    assert change["moment"].astimezone(WARSAW).strftime("%d.%m %H:%M") == "12.11 10:17"


def test_moon_change_after_a_noon_is_the_minute_from_the_spec() -> None:
    change = next_decan_change("Moon", NOON)
    assert (change["from_index"], change["to_index"]) == (24, 25)
    assert change["moment"].astimezone(WARSAW).strftime("%d.%m %H:%M") == "11.11 05:21"


@pytest.mark.parametrize("body", ["Sun", "Moon", "Mercury", "Mars"])
def test_change_is_exact_to_the_second(body: str) -> None:
    change = next_decan_change(body, NOON)
    exact = change["moment_exact"]
    assert exact.microsecond == 0
    assert _index(body, exact - timedelta(seconds=1)) == change["from_index"]
    assert _index(body, exact) == change["to_index"]


def test_sun_stands_on_the_boundary_at_the_change() -> None:
    change = next_decan_change("Sun", NOON)
    lon = body_longitude("Sun", julian_day(change["moment_exact"]))
    # The Sun moves about 0.00001 deg per second.
    assert 230.0 <= lon < 230.0 + 0.00005


def test_moment_is_the_exact_second_rounded_to_the_minute() -> None:
    change = next_decan_change("Sun", NOON)
    assert change["moment"] == to_minute(change["moment_exact"])
    assert change["moment"] == datetime(2026, 11, 12, 9, 17, tzinfo=timezone.utc)


def test_to_minute_rounds_half_up() -> None:
    base = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert to_minute(base + timedelta(seconds=29)) == base
    assert to_minute(base + timedelta(seconds=30)) == base + timedelta(minutes=1)


def test_moment_of_inverts_julian_day_to_the_second() -> None:
    moment = datetime(2026, 3, 1, 7, 8, 9, tzinfo=timezone.utc)
    assert moment_of(julian_day(moment)) == moment


def test_moon_changes_once_on_a_day_in_local_time() -> None:
    day = datetime(2026, 11, 11, 0, 0, tzinfo=WARSAW)
    changes = decan_changes("Moon", day, day + timedelta(days=1))
    assert [(c["from_index"], c["to_index"]) for c in changes] == [(24, 25)]
    assert changes[0]["moment"].astimezone(WARSAW).strftime("%H:%M") == "05:21"


def test_no_change_inside_a_quiet_window() -> None:
    assert decan_changes("Sun", NOON, NOON + timedelta(hours=6)) == []
    assert decan_changes("Sun", NOON, NOON) == []


def test_ascendant_passes_all_36_decans_in_a_day_at_mid_latitude() -> None:
    changes = decan_changes("Ascendant", NOON, NOON + timedelta(days=1), latitude=LAT, longitude=LON)
    assert len(changes) == 36
    assert {c["direction"] for c in changes} == {"forward"}
    assert len({c["to_index"] for c in changes}) == 36
    for change in changes[:3]:
        exact = change["moment_exact"]
        assert _index("Ascendant", exact - timedelta(seconds=1), latitude=LAT, longitude=LON) == change["from_index"]
        assert _index("Ascendant", exact, latitude=LAT, longitude=LON) == change["to_index"]


def test_midheaven_passes_all_36_decans_in_a_day() -> None:
    changes = decan_changes("Midheaven", NOON, NOON + timedelta(days=1), latitude=LAT, longitude=LON)
    assert len(changes) == 36


def test_retrograde_mercury_goes_back_a_decan() -> None:
    year = decan_changes(
        "Mercury",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    backward = [c for c in year if c["direction"] == "backward"]
    assert len(year) == 47
    assert len(backward) == 5
    first = backward[0]
    assert (first["from_index"], first["to_index"]) == (35, 34)
    assert first["moment_exact"] == datetime(2026, 3, 4, 2, 41, 25, tzinfo=timezone.utc)


def test_changes_are_in_time_order_and_chain() -> None:
    changes = decan_changes(
        "Moon", NOON, NOON + timedelta(days=10)
    )
    assert all(a["moment_exact"] < b["moment_exact"] for a, b in zip(changes, changes[1:]))
    assert all(a["to_index"] == b["from_index"] for a, b in zip(changes, changes[1:]))


def test_slow_body_and_short_horizon() -> None:
    assert next_decan_change("Pluto", NOON, horizon_days=1) is None
    change = next_decan_change("Pluto", NOON)
    assert change["moment"] == datetime(2029, 3, 27, 6, 25, tzinfo=timezone.utc)


def test_body_decan_names_the_card() -> None:
    assert body_decan("Sun", NOON)["card"]["id"] == "cups_06"
    moon = body_decan("Moon", NOON)
    assert moon["name"] == "Moon"
    assert moon["card"]["id"] == "wands_08"
    asc = body_decan("Ascendant", NOON, latitude=LAT, longitude=LON)
    assert 0 <= asc["index"] < 36


def test_bad_input_is_refused() -> None:
    with pytest.raises(ValueError):
        next_decan_change("Sun", datetime(2026, 11, 10, 12, 0))
    with pytest.raises(ValueError):
        next_decan_change("Chiron", NOON)
    with pytest.raises(ValueError):
        next_decan_change("Ascendant", NOON)
    with pytest.raises(ValueError):
        decan_changes("Sun", NOON, datetime(2026, 11, 11))
