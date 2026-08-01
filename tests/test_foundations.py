"""Unit tests for Phase 5b foundation modules: Draconic, Numerology and BaZi."""

from datetime import date, time

import pytest

from eldermind_core.services.bazi import compute_bazi
from eldermind_core.services.ephemeris import (
    compute_draconic_chart,
    compute_julian_day_ut,
)
from eldermind_core.services.numerology import (
    compute_day_number,
    compute_expression_number,
    compute_life_path,
    compute_maturity_number,
    compute_numerology,
    compute_personality_number,
    compute_personal_year,
    compute_soul_urge_number,
)


def test_life_path_reduction() -> None:
    """Life Path reduces full birth date digits to a single digit or master number."""
    # 1985-06-15 -> 1+9+8+5+0+6+1+5 = 35 -> 3+5 = 8
    assert compute_life_path(date(1985, 6, 15)) == 8
    # 1990-01-01 -> 1+9+9+0+0+1+0+1 = 21 -> 3
    assert compute_life_path(date(1990, 1, 1)) == 3


def test_life_path_preserves_master_number() -> None:
    """Master numbers 11, 22 and 33 are not reduced further."""
    # Crafted date: 1987-03-27 -> 1+9+8+7+0+3+2+7 = 37 -> 10 -> 1 (not master)
    # Use 1975-04-22 -> 1+9+7+5+0+4+2+2 = 30 -> 3 (not master)
    # Use 1991-11-11 -> 1+9+9+1+1+1+1+1 = 24 -> 6
    # Use 1980-11-29 -> 1+9+8+0+1+1+2+9 = 31 -> 4
    # Use 2008-02-29 -> 2+0+0+8+0+2+2+9 = 23 -> 5
    # Use 1974-08-08 -> 1+9+7+4+0+8+0+8 = 37 -> 10 -> 1
    assert compute_life_path(date(1974, 8, 8)) == 1


def test_personal_year() -> None:
    """Personal Year uses day + month + current year, reduced to 1-9."""
    # 15 June + 2026 = 15 + 6 + 2026 = 2047 -> 2+0+4+7 = 13 -> 4
    assert compute_personal_year(date(1985, 6, 15), date(2026, 1, 1)) == 4


def test_day_number() -> None:
    """Day Number is the reduced birth day, with master numbers preserved."""
    assert compute_day_number(date(1993, 9, 1)) == 1
    assert compute_day_number(date(1985, 6, 15)) == 6
    assert compute_day_number(date(1990, 11, 11)) == 11
    assert compute_day_number(date(1990, 1, 22)) == 22


def test_name_based_numbers_marcin_jonatan_gojdka() -> None:
    """Reference numerology for Marcin Jonatan Gojdka matches the report."""
    name = "Marcin Jonatan Gojdka"
    assert compute_expression_number(name) == 1
    assert compute_soul_urge_number(name) == 7
    assert compute_personality_number(name) == 3


def test_maturity_number() -> None:
    """Maturity Number reduces the sum of Life Path and Expression Number."""
    # Marcin Jonatan Gojdka: Life Path 5 + Expression 1 = 6
    assert compute_maturity_number(5, 1) == 6


def test_compute_numerology_full_profile() -> None:
    """compute_numerology returns all expected fields with correct values."""
    result = compute_numerology(
        birth_date=date(1993, 9, 1),
        current_date=date(2026, 7, 23),
        full_name="Marcin Jonatan Gojdka",
    )
    assert result["life_path"] == 5
    assert result["personal_year"] == 11
    assert result["expression_number"] == 1
    assert result["soul_urge_number"] == 7
    assert result["personality_number"] == 3
    assert result["maturity_number"] == 6
    assert result["day_number"] == 1


def test_polish_diacritics_flattened() -> None:
    """Polish diacritics are flattened to Latin equivalents before summing."""
    # "Michał" and "Michal" must yield the same Expression Number.
    assert compute_expression_number("Michał Łukasiński") == compute_expression_number("Michal Lukasinski")


def test_draconic_node_is_aries_origin() -> None:
    """In the Draconic chart the True North Node must define 0° Aries."""
    jd_ut, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    draconic = compute_draconic_chart(jd_ut)

    node = next(p for p in draconic["planets"] if p["name"] == "TrueNode")
    assert node["draconic_longitude"] == pytest.approx(0.0, abs=1e-5)
    assert node["sign"] == "Aries"


def test_draconic_structure() -> None:
    """Draconic chart must contain all configured planets and the Node longitude."""
    jd_ut, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    draconic = compute_draconic_chart(jd_ut)

    assert "north_node_longitude" in draconic
    assert len(draconic["planets"]) == 11
    names = {p["name"] for p in draconic["planets"]}
    assert "Sun" in names
    assert "TrueNode" in names
    for planet in draconic["planets"]:
        assert 0.0 <= planet["draconic_longitude"] < 360.0
        assert planet["sign"] in [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
        ]


def test_draconic_marcin_sun_in_capricorn() -> None:
    """Marcin's Draconic Sun must fall in Capricorn."""
    jd_ut, _ = compute_julian_day_ut(
        date(1993, 9, 1), time(10, 25), "Europe/Warsaw"
    )
    draconic = compute_draconic_chart(jd_ut)
    sun = next(p for p in draconic["planets"] if p["name"] == "Sun")
    assert sun["sign"] == "Capricorn"


def test_bazi_marcin_year_rooster_day_master_yin_wood() -> None:
    """Marcin's BaZi year animal must be Rooster and day master Yin Wood (Yi)."""
    bazi = compute_bazi(date(1993, 9, 1), time(10, 25))

    assert bazi["year_pillar"]["branch"]["animal"] == "Rooster"
    assert bazi["day_master"]["english"] == "Yi"
    assert bazi["day_master"]["polarity"] == "Yin"
    assert bazi["day_master"]["element"] == "Wood"


def test_bazi_structure() -> None:
    """BaZi output must contain all four pillars and day master."""
    bazi = compute_bazi(date(1985, 6, 15), time(14, 30))

    assert "year_pillar" in bazi
    assert "month_pillar" in bazi
    assert "day_pillar" in bazi
    assert "hour_pillar" in bazi
    assert "day_master" in bazi
    assert bazi["year_pillar"]["stem"]["english"] in [
        "Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"
    ]
    assert bazi["day_master"]["english"] in [
        "Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"
    ]
