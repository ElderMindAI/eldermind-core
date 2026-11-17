"""Unit tests for the BaZi (Four Pillars) service, including Da Yun."""

from datetime import date, datetime, time, timedelta

import pytest
import swisseph as swe

from eldermind_core.services.bazi import (
    HEAVENLY_STEMS_ENGLISH,
    HEAVENLY_STEMS_HANZI,
    TEN_GODS,
    _jie_julian_day,
    _sun_longitude,
    compute_bazi,
    li_chun_julian_day,
    year_pillar_hanzi,
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


# --- Year pillar from Li Chun (ENGINE_VERSION 1.0.7) --------------------------
#
# Invented births only. Until 1.0.7 the year pillar changed at the Chinese New
# Year (cnlunar's `year8Char`), the month pillar at the Jie: between the two
# they contradicted each other.


def _tiger_month_stem(year_stem: str) -> str:
    """五虎遁: the stem of the 寅 month for a year stem (甲己 -> 丙寅, 乙庚 -> 戊寅, ...)."""
    return HEAVENLY_STEMS_HANZI[(HEAVENLY_STEMS_HANZI.index(year_stem) % 5 * 2 + 2) % 10]


_MONTH_BRANCHES = "寅卯辰巳午未申酉戌亥子丑"


def _month_stem_from_year(year_stem: str, month_branch: str) -> str:
    """Month stem the year stem implies, counting on from its 寅 month."""
    offset = _MONTH_BRANCHES.index(month_branch)
    return HEAVENLY_STEMS_HANZI[(HEAVENLY_STEMS_HANZI.index(_tiger_month_stem(year_stem)) + offset) % 10]


def _assert_year_and_month_agree(result: dict) -> None:
    year, month = result["year_pillar"]["hanzi"], result["month_pillar"]["hanzi"]
    assert month[0] == _month_stem_from_year(year[0], month[1]), (year, month)


@pytest.mark.parametrize(
    ("birth", "year", "month", "pre_fix_year"),
    [
        # New Year 2013 fell on 10 Feb, after Li Chun (3 Feb 16:13 UT): a birth
        # in between belongs to 癸巳 already.
        ((date(2013, 2, 6), time(12, 0)), "癸巳", "甲寅", "壬辰"),
        # New Year 2023 fell on 22 Jan, before Li Chun (4 Feb 02:42 UT): a birth
        # in between still belongs to 壬寅.
        ((date(2023, 1, 28), time(12, 0)), "壬寅", "癸丑", "癸卯"),
    ],
)
def test_year_pillar_changes_at_li_chun_not_new_year(
    birth: tuple, year: str, month: str, pre_fix_year: str
) -> None:
    result = compute_bazi(*birth, julian_day_ut=_jd(*birth))

    assert result["year_pillar"]["hanzi"] == year != pre_fix_year
    assert result["month_pillar"]["hanzi"] == month
    _assert_year_and_month_agree(result)


@pytest.mark.parametrize(
    ("birth", "year"),
    [
        # 2013: New Year after Li Chun. Before Li Chun the old year, after it the new.
        ((date(2013, 2, 2), time(12, 0)), "壬辰"),
        ((date(2013, 2, 9), time(12, 0)), "癸巳"),   # the eve of the New Year
        ((date(2013, 2, 11), time(12, 0)), "癸巳"),
        # 2023: New Year before Li Chun. Between them still the old year.
        ((date(2023, 1, 21), time(12, 0)), "壬寅"),
        ((date(2023, 1, 23), time(12, 0)), "壬寅"),  # the day after the New Year
        ((date(2023, 2, 5), time(12, 0)), "癸卯"),
    ],
)
def test_year_pillar_on_both_sides_of_new_year(birth: tuple, year: str) -> None:
    result = compute_bazi(*birth, julian_day_ut=_jd(*birth))

    assert result["year_pillar"]["hanzi"] == year
    _assert_year_and_month_agree(result)


def test_year_pillar_turns_at_the_li_chun_minute() -> None:
    """Li Chun 2024: 4 Feb 08:27:08 UT, 09:27:08 in Warsaw."""
    li_chun = li_chun_julian_day(2024)
    year, month, day, hour = swe.revjul(li_chun)
    assert (year, month, day) == (2024, 2, 4)
    assert int(hour * 60) == 8 * 60 + 27
    assert _sun_longitude(li_chun) == pytest.approx(315.0, abs=1e-6)

    minute = 1 / 1440
    assert year_pillar_hanzi(li_chun - minute) == "癸卯"
    assert year_pillar_hanzi(li_chun + minute) == "甲辰"

    before = compute_bazi(date(2024, 2, 4), time(9, 26), gender="male", julian_day_ut=_jd(date(2024, 2, 4), time(9, 26)))
    after = compute_bazi(date(2024, 2, 4), time(9, 28), gender="male", julian_day_ut=_jd(date(2024, 2, 4), time(9, 28)))
    assert before["year_pillar"]["hanzi"] == "癸卯"
    assert after["year_pillar"]["hanzi"] == "甲辰"
    # The Da Yun direction follows the corrected year stem: male + Yin 癸 runs
    # backward, male + Yang 甲 forward.
    assert before["da_yun_direction"] == "backward"
    assert after["da_yun_direction"] == "forward"


def test_element_count_and_useful_god_use_the_corrected_year() -> None:
    birth = date(2013, 2, 6), time(12, 0)
    result = compute_bazi(*birth, julian_day_ut=_jd(*birth))

    pillars = [result[f"{name}_pillar"] for name in ("year", "month", "day", "hour")]
    expected: dict[str, int] = {"Wood": 0, "Fire": 0, "Earth": 0, "Metal": 0, "Water": 0}
    for pillar in pillars:
        expected[pillar["stem"]["element"]] += 1
        expected[pillar["branch"]["element"]] += 1
    assert result["year_pillar"]["stem"]["element"] == "Water"  # 癸
    assert result["year_pillar"]["branch"]["element"] == "Fire"  # 巳
    assert result["element_count"] == expected


def test_year_and_month_agree_every_day() -> None:
    """五虎遁 for every noon from 15 January to 25 February, 1950-2030, Warsaw.

    The Chinese New Year always falls between 21 January and 20 February, so
    the window holds every birth the pre-1.0.7 engine got wrong. Since 1.0.8
    the Jie days are no exception: the month follows the Sun too.
    """
    checked = 0
    for year in range(1950, 2031):
        day = date(year, 1, 15)
        while day <= date(year, 2, 25):
            _assert_year_and_month_agree(compute_bazi(day, time(12, 0), julian_day_ut=_jd(day, time(12, 0))))
            checked += 1
            day += timedelta(days=1)
    assert checked == 81 * 42


# --- Month pillar from the Jie moment (ENGINE_VERSION 1.0.8) ----------------
#
# Invented births, Warsaw. cnlunar opened the month at local midnight of the
# Beijing date of the Jie; the values marked "cnlunar" are what 1.0.7 said.


@pytest.mark.parametrize(
    ("birth", "year", "month", "cnlunar_month"),
    [
        # Li Chun 2024: 4 Feb 09:27 Warsaw. cnlunar was already in 寅 at midnight.
        ((date(2024, 2, 4), time(6, 0)), "癸卯", "乙丑", "丙寅"),
        ((date(2024, 2, 4), time(9, 27)), "癸卯", "乙丑", "丙寅"),
        ((date(2024, 2, 4), time(9, 28)), "甲辰", "丙寅", "丙寅"),
        # Li Chun 2026: 3 Feb 21:02 Warsaw, already 4 Feb in Beijing: cnlunar late.
        ((date(2026, 2, 3), time(21, 2)), "乙巳", "己丑", "己丑"),
        ((date(2026, 2, 3), time(21, 3)), "丙午", "庚寅", "己丑"),
        ((date(2026, 2, 3), time(23, 0)), "丙午", "庚寅", "己丑"),
        # Jing Zhe 2026: 5 Mar 14:58 Warsaw.
        ((date(2026, 3, 5), time(12, 0)), "丙午", "庚寅", "辛卯"),
        ((date(2026, 3, 5), time(14, 59)), "丙午", "辛卯", "辛卯"),
        # Jing Zhe 2025: 5 Mar 09:07 Warsaw.
        ((date(2025, 3, 5), time(6, 0)), "乙巳", "戊寅", "己卯"),
    ],
)
def test_month_pillar_changes_at_the_jie_moment(
    birth: tuple, year: str, month: str, cnlunar_month: str
) -> None:
    import cnlunar

    result = compute_bazi(*birth, julian_day_ut=_jd(*birth))

    assert result["year_pillar"]["hanzi"] == year
    assert result["month_pillar"]["hanzi"] == month
    _assert_year_and_month_agree(result)
    assert cnlunar.Lunar(datetime.combine(*birth), godType="8char").month8Char == cnlunar_month


def test_month_pillar_agrees_with_cnlunar_away_from_the_jie() -> None:
    """Away from a Jie day the new month is cnlunar's month: only the boundary moved.

    Every noon of 2000-2003, Warsaw, more than a degree of the Sun (about a
    day) from a Jie.
    """
    import cnlunar

    checked = 0
    day = date(2000, 1, 1)
    while day < date(2004, 1, 1):
        jd = _jd(day, time(12, 0))
        if abs(_sun_longitude(jd) % 30.0 - 15.0) > 1.0:  # the Jie sit at 15° + 30°k
            expected = cnlunar.Lunar(datetime.combine(day, time(12, 0)), godType="8char").month8Char
            assert compute_bazi(day, time(12, 0), julian_day_ut=jd)["month_pillar"]["hanzi"] == expected, day
            checked += 1
        day += timedelta(days=1)
    assert checked > 1300


def test_da_yun_steps_from_the_corrected_month() -> None:
    """4 Feb 2024 06:00 Warsaw, male: 癸 (Yin) year, so backward from 乙丑."""
    birth = date(2024, 2, 4), time(6, 0)
    result = compute_bazi(*birth, gender="male", julian_day_ut=_jd(*birth))

    assert result["da_yun_direction"] == "backward"
    assert [p["hanzi"] for p in result["da_yun"][:2]] == ["甲子", "癸亥"]
    # Backward counts the days since the Jie that opened 乙丑 (Xiao Han, 6 Jan
    # 2024), about 29 days, so close to 10 years.
    assert 9.0 < result["da_yun_start_age_precise"] < 10.5



def test_without_julian_day_the_wall_clock_is_read_as_ut() -> None:
    """Documented fallback: only a birth within the zone offset of Li Chun can differ."""
    assert compute_bazi(date(2013, 2, 6), time(12, 0))["year_pillar"]["hanzi"] == "癸巳"
    assert compute_bazi(date(2023, 1, 28), time(12, 0))["year_pillar"]["hanzi"] == "壬寅"


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
