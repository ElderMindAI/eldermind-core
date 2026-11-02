"""Transit facts for the report timeline (ENGINE_VERSION 1.0.5).

The natal points are bare longitudes, two of them from the charts of the
2026-11-02 report check; no birth data. Every date below is a property of the
ephemeris, checked against an hourly scan when the test was written.
"""

from __future__ import annotations

from datetime import date

import pytest

from eldermind_core.services.ephemeris import (
    _longitude_to_nakshatra,
    attach_houses_to_planets,
    compute_all_planets,
    compute_draconic_chart,
    compute_houses,
    compute_transit_windows,
)
from eldermind_core.services.transits import (
    EXACT_ORB,
    aspect_orb,
    compute_planet_returns,
    compute_transit_aspects,
    julian_day_at_noon,
    tropical_longitude,
)

ANGLES = {"Conjunction": 0.0, "Square": 90.0, "Trine": 120.0, "Opposition": 180.0}


def _point(name: str, longitude: float) -> dict:
    return {"name": name, "longitude": longitude}


NATAL = [
    _point("Sun", 100.0),
    _point("Moon", 200.0),
    _point("Jupiter", 136.9215),
    _point("Uranus", 326.245706),
    _point("TrueNode", 50.0),
]
ASCENDANT = _point("Ascendant", 122.026925)
MIDHEAVEN = _point("Midheaven", 7.092129)


def _natal_lon(name: str) -> float:
    return {p["name"]: p["longitude"] for p in [*NATAL, ASCENDANT, MIDHEAVEN]}[name]


@pytest.fixture(scope="module")
def windows() -> list[dict]:
    return compute_transit_windows(NATAL, date(2026, 10, 29), 18, ASCENDANT, MIDHEAVEN, max_windows=200)


def test_every_pass_is_inside_the_scan_and_a_true_minimum(windows: list[dict]) -> None:
    end = date(2026, 10, 29).toordinal() + int(18 * 30.4375)
    for window in windows:
        for entry in window["passes"]:
            assert date(2026, 10, 29) <= date.fromisoformat(entry["date"]) <= date.fromordinal(end)
        if window["event_type"] != "aspect":
            continue
        natal = _natal_lon(window["natal_body"])
        angle = ANGLES[window["aspect"]]
        for entry in window["passes"]:
            moment = julian_day_at_noon(date.fromisoformat(entry["date"]))
            hour = int(entry["moment_utc"][11:13]) + int(entry["moment_utc"][14:16]) / 60.0
            jd = moment - 0.5 + hour / 24.0
            at = aspect_orb(tropical_longitude(jd, window["transit_body"]), natal, angle)
            assert at == pytest.approx(entry["orb"], abs=0.02)
            for offset in (-0.5, 0.5):
                around = aspect_orb(tropical_longitude(jd + offset, window["transit_body"]), natal, angle)
                assert around >= at - 1e-6
            assert entry["exact"] is (entry["orb"] < EXACT_ORB)


def test_a_hit_just_past_the_end_is_not_dated_at_the_end() -> None:
    # Saturn squares this Ascendant on 2028-04-29 (01:00 UT), the day after
    # an 18-month scan from 2026-10-29 ends. 1.0.4 listed it as 2028-04-28.
    found = compute_transit_windows([], date(2026, 10, 29), 18, ASCENDANT, None, max_windows=200)
    assert not [w for w in found if w["transit_body"] == "Saturn" and w["aspect"] == "Square"]
    later = compute_transit_windows([], date(2026, 11, 29), 18, ASCENDANT, None, max_windows=200)
    square = next(w for w in later if w["transit_body"] == "Saturn" and w["aspect"] == "Square")
    assert square["passes"][-1]["date"] == "2028-04-29"
    assert square["passes"][-1]["exact"] is True


def test_a_station_short_of_the_degree_is_not_exact(windows: list[dict]) -> None:
    saturn_mc = next(
        w for w in windows
        if w["transit_body"] == "Saturn" and w["natal_body"] == "Midheaven" and w["aspect"] == "Conjunction"
    )
    assert saturn_mc["exact"] is False
    assert saturn_mc["orb"] == pytest.approx(0.84, abs=0.02)
    assert saturn_mc["event_date"] == "2026-12-10"


def test_retrograde_passes_stay_in_one_window(windows: list[dict]) -> None:
    neptune_mc = next(
        w for w in windows
        if w["transit_body"] == "Neptune" and w["natal_body"] == "Midheaven"
    )
    assert [(p["date"], p["exact"]) for p in neptune_mc["passes"]] == [
        ("2027-07-09", False),
        ("2028-04-16", True),
    ]


def test_yearly_returns_of_the_sun_are_separate_windows(windows: list[dict]) -> None:
    sun_on_sun = [
        w for w in windows
        if w["transit_body"] == "Sun" and w["natal_body"] == "Sun"
    ]
    assert len(sun_on_sun) >= 1
    assert all(len(w["passes"]) == 1 for w in sun_on_sun)


def test_node_wobble_makes_one_pass_per_event(windows: list[dict]) -> None:
    for window in windows:
        if window["transit_body"] != "TrueNode":
            continue
        dates = [date.fromisoformat(p["date"]) for p in window["passes"]]
        assert all((b - a).days > 30 for a, b in zip(dates, dates[1:]))


def test_each_sign_entered_is_its_own_ingress(windows: list[dict]) -> None:
    jupiter = [w for w in windows if w["event_type"] == "ingress" and w["transit_body"] == "Jupiter"]
    assert [w["sign"] for w in jupiter] == ["Virgo"]
    assert jupiter[0]["event_date"] == "2027-07-26"


def test_transit_aspects_name_the_aspect_the_engine_measures() -> None:
    # Jupiter at 24° Leo and a natal Uranus at 26° Aquarius: an applying
    # opposition, exact on 2026-11-20. The report called it a trine.
    jd = julian_day_at_noon(date(2026, 11, 2))
    aspects = compute_transit_aspects(NATAL, jd, ASCENDANT, MIDHEAVEN)
    jupiter_uranus = [
        a for a in aspects if a["transit_body"] == "Jupiter" and a["natal_body"] == "Uranus"
    ]
    assert len(jupiter_uranus) == 1
    entry = jupiter_uranus[0]
    assert entry["aspect"] == "Opposition"
    assert entry["applying"] is True
    assert entry["orb"] == pytest.approx(1.74, abs=0.02)
    assert entry["closest"]["date"] == "2026-11-20"
    assert entry["closest"]["exact"] is True
    assert not [a for a in aspects if a["transit_body"] == "Moon"]
    assert aspects == sorted(aspects, key=lambda a: a["orb"])


def test_jupiter_return_in_progress_with_its_station() -> None:
    jd = julian_day_at_noon(date(2026, 11, 2))
    birth = jd - 23.84 * 365.25
    returns = {r["body"]: r for r in compute_planet_returns(NATAL, jd, birth)}
    jupiter = returns["Jupiter"]
    assert jupiter["status"] == "in_progress"
    assert jupiter["return_number"] == 2
    assert jupiter["passes"][0]["date"] == "2026-09-16"
    assert jupiter["passes"][0]["exact"] is True
    station = next(s for s in jupiter["stations"] if s["date"] == "2027-04-13")
    assert station["kind"] == "direct"
    assert station["orb_to_natal"] < 0.1
    assert "Saturn" not in returns  # no natal Saturn given


def test_navamsa_sign_of_each_pada() -> None:
    pushya_pada_2 = 7 * 360.0 / 27 + 360.0 / 108 + 1.0
    assert _longitude_to_nakshatra(pushya_pada_2)["nakshatra_name"] == "Pushya"
    assert _longitude_to_nakshatra(pushya_pada_2)["pada"] == 2
    assert _longitude_to_nakshatra(pushya_pada_2)["navamsa_sign"] == "Virgo"
    assert _longitude_to_nakshatra(1.0)["navamsa_sign"] == "Aries"
    assert _longitude_to_nakshatra(359.0)["navamsa_sign"] == "Pisces"
    # 108 padas run through the signs nine times.
    signs = [_longitude_to_nakshatra(i * 360.0 / 108 + 0.5)["navamsa_sign"] for i in range(108)]
    assert signs[:12] == signs[12:24] == signs[96:108]


def test_windows_carry_the_natal_house_of_the_transiting_body() -> None:
    # Without it M9 placed Saturn's ingress into Taurus in the 8th house of a
    # chart whose 8th cusp is at 22° Taurus.
    jd = julian_day_at_noon(date(1993, 5, 17))
    _, _, houses = compute_houses(jd, 52.23, 21.01)
    found = compute_transit_windows(
        NATAL, date(2026, 10, 29), 18, ASCENDANT, MIDHEAVEN, max_windows=200, house_cusps=houses,
    )
    for window in found:
        assert window["natal_house"] == window["passes"][0]["natal_house"]
        for entry in window["passes"]:
            hour = int(entry["moment_utc"][11:13]) + int(entry["moment_utc"][14:16]) / 60.0
            moment = julian_day_at_noon(date.fromisoformat(entry["date"])) - 0.5 + hour / 24.0
            expected = attach_houses_to_planets(
                [{"name": window["transit_body"], "longitude": tropical_longitude(moment, window["transit_body"])}],
                houses,
            )[0]["house_number"]
            assert entry["natal_house"] == expected
    ingress = next(w for w in found if w["event_type"] == "ingress")
    assert f"dom natalny {ingress['natal_house']}" in ingress["description"]
    plain = compute_transit_windows(NATAL, date(2026, 10, 29), 18, ASCENDANT, MIDHEAVEN, max_windows=200)
    assert all("natal_house" not in w and all("natal_house" not in p for p in w["passes"]) for w in plain)


def test_draconic_houses_are_the_natal_houses() -> None:
    jd = julian_day_at_noon(date(1993, 5, 17))
    _, _, houses = compute_houses(jd, 52.23, 21.01)
    natal = {p["name"]: p["house_number"] for p in attach_houses_to_planets(compute_all_planets(jd), houses)}
    draconic = compute_draconic_chart(jd, house_cusps=houses)
    assert {p["name"]: p["house_number"] for p in draconic["planets"]} == natal
    assert "house_number" not in compute_draconic_chart(jd)["planets"][0]
