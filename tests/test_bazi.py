"""Unit tests for the BaZi (Four Pillars) service, including Da Yun."""

from datetime import date, datetime, time, timedelta

import pytest
import swisseph as swe

from eldermind_core.services.bazi import (
    HEAVENLY_STEMS_ENGLISH,
    TEN_GODS,
    _jie_julian_day,
    _sun_longitude,
    compute_bazi,
)
from eldermind_core.services.ephemeris import compute_julian_day_ut


def _god(day_master: str, stem: str) -> str:
    return TEN_GODS[HEAVENLY_STEMS_ENGLISH.index(day_master)][HEAVENLY_STEMS_ENGLISH.index(stem)]


# Textbook pairs, one per relationship and polarity — the first block are cells
# the hand-written table had wrong until 2026-10-23 (32 of 100 were).
@pytest.mark.parametrize(
    ("day_master", "stem", "expected"),
    [
        ("Jia", "Geng", "Seven Killings"),   # 庚 is 甲's 七殺: Metal cuts Wood
        ("Yi", "Geng", "Direct Officer"),    # 乙庚合: Geng is Yi's 正官
        ("Yi", "Xin", "Seven Killings"),
        ("Yi", "Ren", "Direct Seal"),        # Water feeds Wood: resource
        ("Yi", "Gui", "Partial Seal"),
        ("Geng", "Jia", "Indirect Wealth"),  # Metal controls Wood: wealth
        ("Geng", "Bing", "Seven Killings"),  # Fire melts Metal
        ("Ren", "Jia", "Food God"),          # Water produces Wood: output
        ("Ren", "Wu", "Seven Killings"),     # Earth dams Water
        ("Gui", "Ji", "Seven Killings"),
        ("Bing", "Ren", "Seven Killings"),   # right before the fix too
        ("Wu", "Bing", "Partial Seal"),
        ("Ding", "Geng", "Direct Wealth"),
        ("Ji", "Xin", "Food God"),
    ],
)
def test_ten_gods_follow_the_five_element_cycles(day_master: str, stem: str, expected: str) -> None:
    assert _god(day_master, stem) == expected


def test_every_day_master_sees_each_god_exactly_once() -> None:
    """Ten stems, ten gods: each row is a permutation, with Bi Jian on the diagonal."""
    for index, row in enumerate(TEN_GODS):
        assert len(set(row)) == 10
        assert row[index] == "Bi Jian"


def test_bazi_structure_and_day_master() -> None:
    """BaZi result must contain the four pillars and a Day Master."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30))

    assert "year_pillar" in result
    assert "month_pillar" in result
    assert "day_pillar" in result
    assert "hour_pillar" in result
    assert result["day_master"]["english"] == "Yi"
    assert result["day_master"]["element"] == "Wood"


def test_bazi_element_count_and_useful_god() -> None:
    """Element count and Useful God must be deterministic."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30))

    assert set(result["element_count"].keys()) == {"Wood", "Fire", "Earth", "Metal", "Water"}
    total = sum(result["element_count"].values())
    assert total == 8  # 4 stems + 4 branches

    useful = result["useful_god"]
    assert useful["day_master_strength"] in {"weak", "strong"}
    assert useful["useful_element"] in {"Wood", "Fire", "Earth", "Metal", "Water"}


def test_bazi_ten_gods_present() -> None:
    """Every pillar must expose its Ten Gods relationships."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30))

    for key in ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"):
        pillar = result[key]
        assert "ten_gods" in pillar
        assert "stem_ten_god" in pillar["ten_gods"]
        assert "hidden_stems_ten_gods" in pillar["ten_gods"]


def test_da_yun_forward_for_male_yang_year() -> None:
    """A male born in a Yang year follows the month pillar forward."""
    # 1985 is Yi-Chou (Yin Wood -> Yin year); male + Yin year = backward.
    # Use 1984 Jia-Zi (Yang Wood -> Yang year) for forward.
    result = compute_bazi(date(1984, 6, 15), time(14, 30), gender="male")

    assert result["da_yun_direction"] == "forward"
    assert result["da_yun_start_age"] in {3, 4}
    assert len(result["da_yun"]) == 8

    # Each pillar should span 10 years and the first starts at start_age.
    first = result["da_yun"][0]
    assert first["start_age"] == result["da_yun_start_age"]
    assert first["end_age"] == first["start_age"] + 9

    # The first pillar is the one AFTER the month pillar, never the month
    # pillar itself (until 2026-10-29 this test pinned the wrong behaviour).
    assert result["month_pillar"]["hanzi"] == "庚午"
    assert [p["hanzi"] for p in result["da_yun"][:3]] == ["辛未", "壬申", "癸酉"]


def test_da_yun_backward_for_female_yang_year() -> None:
    """A female born in a Yang year follows the month pillar backward."""
    result = compute_bazi(date(1984, 6, 15), time(14, 30), gender="female")

    assert result["da_yun_direction"] == "backward"
    assert len(result["da_yun"]) == 8
    assert [p["hanzi"] for p in result["da_yun"][:3]] == ["己巳", "戊辰", "丁卯"]


def test_da_yun_backward_for_male_yin_year() -> None:
    """A male born in a Yin year follows the month pillar backward."""
    # 1985 is Yi-Chou -> Yin year.
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender="male")

    assert result["da_yun_direction"] == "backward"
    assert len(result["da_yun"]) == 8


def test_da_yun_forward_for_female_yin_year() -> None:
    """A female born in a Yin year follows the month pillar forward."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender="female")

    assert result["da_yun_direction"] == "forward"
    assert len(result["da_yun"]) == 8


def test_da_yun_assumed_direction_when_gender_missing() -> None:
    """Without gender, Da Yun falls back to forward with an assumed flag."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender=None)

    assert result["da_yun_direction"] == "forward"
    assert result["da_yun_direction_assumed"] is True
    assert len(result["da_yun"]) == 8


def test_da_yun_direction_not_assumed_when_gender_given() -> None:
    """When gender is provided, direction must not be flagged as assumed."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender="female")

    assert result["da_yun_direction_assumed"] is False


def _jd(day: date, local: time, zone: str = "Europe/Warsaw") -> float:
    return compute_julian_day_ut(birth_date=day, birth_time=local, timezone_name=zone)[0]


@pytest.mark.parametrize(
    ("jd_ut", "forward", "expected_beijing", "expected_longitude"),
    [
        # Almanac times are Beijing time (UT+8).
        # 1986: Xiao Shu (105°) 7 July 18:01, Li Qiu (135°) 8 August 03:46.
        (_jd(date(1986, 7, 19), time(5, 39)), False, datetime(1986, 7, 7, 18, 1), 105.0),
        (_jd(date(1986, 7, 19), time(5, 39)), True, datetime(1986, 8, 8, 3, 46), 135.0),
        # Li Chun (315°) opens the year: 4 February 2024 16:27.
        (_jd(date(2024, 2, 20), time(12, 0)), False, datetime(2024, 2, 4, 16, 27), 315.0),
    ],
)
def test_jie_solar_terms_land_on_their_almanac_times(
    jd_ut: float, forward: bool, expected_beijing: datetime, expected_longitude: float
) -> None:
    jd = _jie_julian_day(jd_ut, forward)
    assert _sun_longitude(jd) == pytest.approx(expected_longitude, abs=1e-4)
    year, month, day, hour = swe.revjul(jd + 8 / 24)
    beijing = datetime(year, month, day) + timedelta(hours=hour)
    assert abs((beijing - expected_beijing).total_seconds()) < 120


def test_da_yun_female_yang_year_textbook_case() -> None:
    """Woman, Bing Yin year (Yang), month Yi Wei, born 12 days after Xiao Shu.

    Backward from Yi Wei: Jia Wu, Gui Si, Ren Chen, Xin Mao, Geng Yin...
    12 days / 3 = 4 years. The pre-fix engine said Wu Xu for ages 34-43.
    """
    birth = date(1986, 7, 19), time(5, 39)
    result = compute_bazi(*birth, gender="female", julian_day_ut=_jd(*birth))

    assert result["month_pillar"]["hanzi"] == "乙未"
    assert result["da_yun_direction"] == "backward"
    assert [p["hanzi"] for p in result["da_yun"][:5]] == ["甲午", "癸巳", "壬辰", "辛卯", "庚寅"]
    assert result["da_yun_start_age_precise"] == pytest.approx(3.9, abs=0.15)
    assert result["da_yun_start_age"] == 4
    assert result["da_yun_start_age_approximate"] is False
    fourth = result["da_yun"][3]
    assert (fourth["start_age"], fourth["end_age"]) == (34, 43)


def test_da_yun_start_age_flagged_approximate_without_julian_day() -> None:
    result = compute_bazi(date(1986, 7, 19), time(5, 39), gender="female")

    assert result["da_yun_start_age_approximate"] is True
    assert result["da_yun_start_age_precise"] is None


def test_da_yun_pillars_contain_ten_gods() -> None:
    """Each Da Yun pillar must include Ten Gods for interpretation."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender="female")

    for pillar in result["da_yun"]:
        assert "start_age" in pillar
        assert "end_age" in pillar
        assert "stem" in pillar
        assert "branch" in pillar
        assert "ten_gods" in pillar
        assert "stem_ten_god" in pillar["ten_gods"]
