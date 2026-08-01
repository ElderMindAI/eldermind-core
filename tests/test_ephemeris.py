"""Unit tests for the astronomical engine.

Split out of the report backend during the core extraction: everything here
exercises `eldermind_core` directly, with no FastAPI involved. The endpoint-level
assertions that used to live alongside these now sit in the report backend's
`tests/test_chart_endpoint.py`.
"""

from datetime import date, time

import pytest

from eldermind_core.core.config import NAKSHATRA_BODIES
from eldermind_core.services.ephemeris import (
    compute_all_planets,
    compute_houses,
    compute_julian_day_ut,
    compute_planet_position,
    compute_vedic_chart,
    compute_vedic_whole_sign_houses,
    compute_western_aspects,
    _longitude_to_nakshatra,
)
from eldermind_core.services.sade_sati import compute_sade_sati
from eldermind_core.services.vedic_dasha import compute_avakahada_chakra


def test_julian_day_conversion() -> None:
    """UTC conversion must produce a reasonable Julian Day for a known date."""
    jd_ut, utc_dt = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )

    assert utc_dt.year == 1985
    # In June Poland is on UTC+2 (CEST), so 14:30 local should be 12:30 UTC.
    assert utc_dt.hour == 12
    assert utc_dt.minute == 30
    # JD for 1985-06-15 12:30 UT should be around 2_446_200.
    assert 2_446_000 < jd_ut < 2_447_000


def test_unknown_timezone_raises() -> None:
    """An invalid IANA timezone must raise a clear ValueError."""
    with pytest.raises(ValueError, match="Unknown or unsupported timezone"):
        compute_julian_day_ut(date(1985, 6, 15), time(0, 0), "Mars/ Olympus")


def test_planet_position_structure() -> None:
    """Planet position output must contain all expected keys and valid ranges."""
    jd_ut, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    sun = compute_planet_position(jd_ut, "Sun", 0)

    assert sun["name"] == "Sun"
    assert 0.0 <= sun["longitude"] < 360.0
    assert sun["sign"] in [
        "Aries",
        "Taurus",
        "Gemini",
        "Cancer",
        "Leo",
        "Virgo",
        "Libra",
        "Scorpio",
        "Sagittarius",
        "Capricorn",
        "Aquarius",
        "Pisces",
    ]
    assert 0.0 <= sun["degree_in_sign"] < 30.0
    assert isinstance(sun["is_retrograde"], bool)


def test_all_planets_computed() -> None:
    """All configured planets and points must be returned."""
    jd_ut, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    planets = compute_all_planets(jd_ut)

    names = {p["name"] for p in planets}
    expected = {
        "Sun",
        "Moon",
        "Mercury",
        "Venus",
        "Mars",
        "Jupiter",
        "Saturn",
        "Uranus",
        "Neptune",
        "Pluto",
        "TrueNode",
    }
    assert names == expected

    for planet in planets:
        assert 0.0 <= planet["longitude"] < 360.0
        assert 0.0 <= planet["degree_in_sign"] < 30.0


def test_houses_structure() -> None:
    """Twelve Placidus house cusps plus Ascendant/MC must be returned."""
    jd_ut, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    ascendant, midheaven, houses = compute_houses(
        jd_ut, latitude=52.2297, longitude=21.0122
    )

    assert ascendant["name"] == "Ascendant"
    assert 0.0 <= ascendant["longitude"] < 360.0

    assert midheaven["name"] == "Midheaven"
    assert 0.0 <= midheaven["longitude"] < 360.0

    assert len(houses) == 12
    for house in houses:
        assert 1 <= house["house_number"] <= 12
        assert 0.0 <= house["longitude"] < 360.0
        assert 0.0 <= house["degree_in_sign"] < 30.0


def test_western_aspects_detection() -> None:
    """Aspect detection must find known Ptolemaic aspects within the orb."""
    jd_ut, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    planets = compute_all_planets(jd_ut)
    aspects = compute_western_aspects(planets)

    assert isinstance(aspects, list)
    # Each aspect must reference real planets and a known aspect type.
    for aspect in aspects:
        assert aspect["planet_1"] != aspect["planet_2"]
        assert aspect["aspect"] in {"Conjunction", "Sextile", "Square", "Trine", "Opposition"}
        assert 0.0 <= aspect["orb_variance"] <= 8.0


def test_vedic_ayanamsa_applied() -> None:
    """Sidereal (Lahiri) Sun longitude should be ~24 degrees less than tropical."""
    jd_ut, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    tropical_sun = compute_planet_position(jd_ut, "Sun", 0, sidereal=False)
    sidereal_sun = compute_planet_position(jd_ut, "Sun", 0, sidereal=True)

    difference = (tropical_sun["longitude"] - sidereal_sun["longitude"]) % 360.0
    # Lahiri ayanamsa for 1985 is roughly 23.5 degrees.
    assert 20.0 < difference < 30.0


def test_vedic_whole_sign_houses() -> None:
    """Whole Sign houses must start from the Ascendant's sign and cycle Aries-Pisces."""
    houses = compute_vedic_whole_sign_houses("Libra")

    assert len(houses) == 12
    assert houses[0]["sign"] == "Libra"
    assert houses[1]["sign"] == "Scorpio"
    assert houses[11]["sign"] == "Virgo"
    assert houses[0]["degree_in_sign"] == 0.0


def test_vedic_chart_structure() -> None:
    """Vedic chart section must contain Lahiri ayanamsa, Lagna, MC, houses and planets."""
    jd_ut, utc_dt = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    vedic = compute_vedic_chart(
        jd_ut, latitude=52.2297, longitude=21.0122, birth_dt=utc_dt
    )

    assert vedic["system"] == "Lahiri (Chitra Paksha)"
    assert 20.0 < vedic["ayanamsa"] < 30.0
    assert vedic["ascendant"]["name"] == "Ascendant"
    assert vedic["midheaven"]["name"] == "Midheaven"
    assert len(vedic["houses"]) == 12
    assert len(vedic["planets"]) == 11
    assert vedic["vimshottari_dasha"]["moon_nakshatra_lord"] in {
        "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    }


def test_retrograde_detection() -> None:
    """Mercury is retrograde on 2024-01-01; the flag must reflect it."""
    jd_ut, _ = compute_julian_day_ut(date(2024, 1, 1), time(0, 0), "UTC")
    mercury = compute_planet_position(jd_ut, "Mercury", 2)

    assert mercury["name"] == "Mercury"
    assert mercury["is_retrograde"] is True


def test_nakshatra_mapping() -> None:
    """Longitude to Nakshatra mapping must cover all 27 mansions correctly."""
    # 0 degrees Aries -> Ashwini, Pada 1
    first = _longitude_to_nakshatra(0.0)
    assert first["nakshatra_number"] == 1
    assert first["nakshatra_name"] == "Ashwini"
    assert first["pada"] == 1

    # 13.3333 degrees -> start of Bharani, Pada 1
    second = _longitude_to_nakshatra(360.0 / 27.0)
    assert second["nakshatra_number"] == 2
    assert second["nakshatra_name"] == "Bharani"
    assert second["pada"] == 1

    # 359.999 degrees -> Revati, Pada 4
    last = _longitude_to_nakshatra(359.999)
    assert last["nakshatra_number"] == 27
    assert last["nakshatra_name"] == "Revati"
    assert last["pada"] == 4


def test_vedic_nakshatras_for_key_bodies() -> None:
    """Vedic chart section must return Nakshatra data for Sun, Moon and Ascendant."""
    jd_ut, utc_dt = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    vedic = compute_vedic_chart(
        jd_ut, latitude=52.2297, longitude=21.0122, birth_dt=utc_dt
    )

    assert "nakshatras" in vedic
    names = {n["name"] for n in vedic["nakshatras"]}
    assert names >= NAKSHATRA_BODIES

    for body in vedic["nakshatras"]:
        if body["name"] in NAKSHATRA_BODIES:
            assert 1 <= body["nakshatra_number"] <= 27
            assert 1 <= body["pada"] <= 4
            assert body["nakshatra_name"] != ""


def test_sade_sati_aquarius_setting_in_2026() -> None:
    """Aquarius Moon in mid-2026 should be in the setting phase of Sade-Sati."""
    result = compute_sade_sati("Aquarius", date(2026, 7, 28))

    assert result["status"] == "active"
    assert result["phase"] == "setting"
    assert result["moon_sign"] == "Aquarius"
    assert result["saturn_sign"] == "Pisces"
    assert result["interpretation_ready"] is True

    # Full window should span roughly 7.5 years around 2020-2027.
    start = date.fromisoformat(result["start_date"])
    end = date.fromisoformat(result["end_date"])
    assert start.year <= 2020
    assert end.year >= 2027

    phase_starts = {p["phase"]: p["start"] for p in result["phases"]}
    assert "rising" in phase_starts
    assert "peak" in phase_starts
    assert "setting" in phase_starts


def test_sade_sati_aries_rising_in_2026() -> None:
    """Aries Moon in mid-2026 should be entering the rising phase."""
    result = compute_sade_sati("Aries", date(2026, 7, 28))

    assert result["status"] == "active"
    assert result["phase"] == "rising"
    assert result["phases"][0]["sign"] == "Pisces"
    assert result["phases"][1]["sign"] == "Aries"
    assert result["phases"][2]["sign"] == "Taurus"


def test_sade_sati_inactive_finds_next_window() -> None:
    """Leo Moon in mid-2026 is not in Sade-Sati; the next window should be reported."""
    result = compute_sade_sati("Leo", date(2026, 7, 28))

    assert result["status"] == "inactive"
    assert result["phase"] is None
    next_start = date.fromisoformat(result["start_date"])
    assert next_start.year > 2026


def test_avakahada_chakra_mappings() -> None:
    """Avakahada Chakra attributes must be derived from the Moon's Nakshatra."""
    shatabhisha = compute_avakahada_chakra("Shatabhisha")
    assert shatabhisha["gana"] == "Rakshasa"
    assert shatabhisha["yoni"] == "Koń"
    assert shatabhisha["nadi"] == "Vata"
    assert shatabhisha["varna"] == "Brahmin"

    rohini = compute_avakahada_chakra("Rohini")
    assert rohini["gana"] == "Manushya"
    assert rohini["nadi"] == "Kapha"
