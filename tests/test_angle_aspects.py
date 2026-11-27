"""Aspects from the planets to the Ascendant and the Midheaven (`compute_angle_aspects`).

The hand-made cases pin the arithmetic: the same five Ptolemaic aspects and the
same 8° orb as `compute_western_aspects`, the orb boundary, the wrap at 0°/360°,
and no Ascendant-Midheaven pair.
"""

from datetime import date, time

import pytest

from eldermind_core.core.config import DEFAULT_ORB_DEGREES, PLANET_IDS
from eldermind_core.services.ephemeris import (
    ANGLE_NAMES,
    compute_all_planets,
    compute_angle_aspects,
    compute_houses,
    compute_julian_day_ut,
    compute_western_aspects,
)


def _p(name: str, lon: float) -> dict:
    return {"name": name, "longitude": lon}


def _pairs(aspects: list[dict]) -> dict[tuple[str, str], tuple[str, float]]:
    return {(a["planet_1"], a["planet_2"]): (a["aspect"], a["orb_variance"]) for a in aspects}


def test_hand_computed_case() -> None:
    """ASC 100°, MC 10°: every pair checked by hand."""
    planets = [
        _p("Sun", 223.0),   # ASC: 123° -> trine 3.0; MC: 213° = 147° -> nothing
        _p("Moon", 5.0),    # ASC: 95° -> square 5.0; MC: 5° -> conjunction 5.0
        _p("Mars", 281.5),  # ASC: 181.5° = 178.5° -> opposition 1.5; MC: 271.5° = 88.5° -> square 1.5
        _p("Venus", 40.0),  # ASC: 60° -> sextile 0.0; MC: 30° -> nothing
    ]
    got = _pairs(compute_angle_aspects(planets, _p("Ascendant", 100.0), _p("Midheaven", 10.0)))
    assert got == {
        ("Sun", "Ascendant"): ("Trine", 3.0),
        ("Moon", "Ascendant"): ("Square", 5.0),
        ("Moon", "Midheaven"): ("Conjunction", 5.0),
        ("Mars", "Ascendant"): ("Opposition", 1.5),
        ("Mars", "Midheaven"): ("Square", 1.5),
        ("Venus", "Ascendant"): ("Sextile", 0.0),
    }


def test_sorted_by_orb() -> None:
    planets = [_p("Sun", 223.0), _p("Moon", 5.0), _p("Mars", 281.5), _p("Venus", 40.0)]
    aspects = compute_angle_aspects(planets, _p("Ascendant", 100.0), _p("Midheaven", 10.0))
    orbs = [a["orb_variance"] for a in aspects]
    assert orbs == sorted(orbs)
    assert aspects[0] == {"planet_1": "Venus", "planet_2": "Ascendant", "aspect": "Sextile", "orb_variance": 0.0}


@pytest.mark.parametrize(
    ("lon", "expected"),
    [
        (168.0, ("Sextile", 8.0)),  # exactly 8° off the sextile: inside
        (168.001, None),            # 8.001° off: outside
        (32.0, ("Sextile", 8.0)),   # the same on the other side of the Ascendant
        (31.999, None),
    ],
)
def test_orb_boundary(lon: float, expected: tuple[str, float] | None) -> None:
    aspects = compute_angle_aspects([_p("Saturn", lon)], _p("Ascendant", 100.0), _p("Midheaven", 250.0))
    got = _pairs(aspects).get(("Saturn", "Ascendant"))
    assert got == expected


def test_wrap_through_zero() -> None:
    """355° and 2° are 7° apart, not 353°."""
    aspects = compute_angle_aspects([_p("Jupiter", 2.0)], _p("Ascendant", 355.0), _p("Midheaven", 178.0))
    assert _pairs(aspects) == {
        ("Jupiter", "Ascendant"): ("Conjunction", 7.0),
        ("Jupiter", "Midheaven"): ("Opposition", 4.0),
    }


def test_no_pair_between_the_angles_and_only_engine_bodies() -> None:
    """ASC and MC in an exact square still produce no ASC-MC aspect; unknown bodies are skipped."""
    planets = [_p("Chiron", 100.0), _p("SouthNode", 100.0), _p("Ascendant", 100.0), _p("TrueNode", 100.0)]
    aspects = compute_angle_aspects(planets, _p("Ascendant", 100.0), _p("Midheaven", 10.0))
    assert _pairs(aspects) == {
        ("TrueNode", "Ascendant"): ("Conjunction", 0.0),
        ("TrueNode", "Midheaven"): ("Square", 0.0),
    }
    for a in aspects:
        assert a["planet_1"] in PLANET_IDS
        assert a["planet_2"] in ANGLE_NAMES


def test_custom_orb() -> None:
    aspects = compute_angle_aspects([_p("Sun", 105.0)], _p("Ascendant", 100.0), _p("Midheaven", 10.0), orb=4.0)
    assert aspects == []


def test_real_chart_matches_western_arithmetic() -> None:
    """On a real chart every angle aspect equals what the planet-planet code gives for the same longitudes."""
    jd_ut, _ = compute_julian_day_ut(date(1985, 6, 15), time(14, 30), "Europe/Warsaw")
    ascendant, midheaven, _houses = compute_houses(jd_ut, latitude=52.2297, longitude=21.0122)
    planets = compute_all_planets(jd_ut)
    aspects = compute_angle_aspects(planets, ascendant, midheaven)

    assert aspects, "a real chart should have at least one aspect to an angle"
    assert len(aspects) <= 2 * len(PLANET_IDS)
    lon = {p["name"]: p["longitude"] for p in planets}
    for a in aspects:
        angle = ascendant if a["planet_2"] == "Ascendant" else midheaven
        # The same pair run through the planet-planet function, with the angle
        # dressed up as a planet of a known name.
        twin = compute_western_aspects([_p(a["planet_1"], lon[a["planet_1"]]), _p("Sun" if a["planet_1"] != "Sun" else "Moon", angle["longitude"])])
        assert len(twin) == 1
        assert (twin[0]["aspect"], twin[0]["orb_variance"]) == (a["aspect"], a["orb_variance"])
        assert 0.0 <= a["orb_variance"] <= DEFAULT_ORB_DEGREES
