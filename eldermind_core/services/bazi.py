"""BaZi (Four Pillars of Destiny).

The year and month pillars change at Li Chun and the other Jie (the Sun at
315° + 30°k, Swiss Ephemeris, to the moment in UT); the day and hour pillars
come from the ``cnlunar`` package on the local wall clock. See `four_pillars`.
"""

import math
from datetime import date, datetime, time, timedelta
from typing import Final

import cnlunar
import swisseph as swe
from cnlunar.config import the60HeavenlyEarth, theHalf60HeavenlyEarth5ElementsList

from eldermind_core.core.reference import resolve_reference_date

HEAVENLY_STEMS_HANZI: Final[list[str]] = [
    "甲",  # Jia
    "乙",  # Yi
    "丙",  # Bing
    "丁",  # Ding
    "戊",  # Wu
    "己",  # Ji
    "庚",  # Geng
    "辛",  # Xin
    "壬",  # Ren
    "癸",  # Gui
]

HEAVENLY_STEMS_ENGLISH: Final[list[str]] = [
    "Jia",
    "Yi",
    "Bing",
    "Ding",
    "Wu",
    "Ji",
    "Geng",
    "Xin",
    "Ren",
    "Gui",
]

STEM_POLARITY: Final[dict[str, str]] = {
    "Jia": "Yang",
    "Yi": "Yin",
    "Bing": "Yang",
    "Ding": "Yin",
    "Wu": "Yang",
    "Ji": "Yin",
    "Geng": "Yang",
    "Xin": "Yin",
    "Ren": "Yang",
    "Gui": "Yin",
}

ELEMENTS: Final[dict[str, str]] = {
    "Jia": "Wood",
    "Yi": "Wood",
    "Bing": "Fire",
    "Ding": "Fire",
    "Wu": "Earth",
    "Ji": "Earth",
    "Geng": "Metal",
    "Xin": "Metal",
    "Ren": "Water",
    "Gui": "Water",
}

BRANCH_ELEMENTS: Final[dict[str, str]] = {
    "子": "Water",
    "丑": "Earth",
    "寅": "Wood",
    "卯": "Wood",
    "辰": "Earth",
    "巳": "Fire",
    "午": "Fire",
    "未": "Earth",
    "申": "Metal",
    "酉": "Metal",
    "戌": "Earth",
    "亥": "Water",
}

ZODIAC_ANIMALS: Final[dict[str, str]] = {
    "子": "Rat",
    "丑": "Ox",
    "寅": "Tiger",
    "卯": "Rabbit",
    "辰": "Dragon",
    "巳": "Snake",
    "午": "Horse",
    "未": "Goat",
    "申": "Monkey",
    "酉": "Rooster",
    "戌": "Dog",
    "亥": "Pig",
}

# Hidden heavenly stems stored inside each earthly branch (Zhi Cang Gan).
# Order matters: main hidden stem first, then secondary, then tertiary.
HIDDEN_STEMS: Final[dict[str, tuple[str, ...]]] = {
    "子": ("癸",),
    "丑": ("己", "癸", "辛"),
    "寅": ("甲", "丙", "戊"),
    "卯": ("乙",),
    "辰": ("戊", "乙", "癸"),
    "巳": ("丙", "庚", "戊"),
    "午": ("丁", "己"),
    "未": ("己", "丁", "乙"),
    "申": ("庚", "壬", "戊"),
    "酉": ("辛",),
    "戌": ("戊", "辛", "丁"),
    "亥": ("壬", "甲"),
}

# Ten Gods relationship of a stem to the Day Master stem.
# Indexed as TEN_GODS[day_master_index][stem_index].
#
# Derived, not typed in. Until 2026-10-23 this was a hand-written 10×10 table
# with 32 wrong cells: the Wood rows had Metal and Water swapped (Geng against
# Jia came out "Partial Seal" instead of Seven Killings), and the Metal and
# Water rows were wrong for every element but their own and their resource.
# Only the Fire and Earth rows were right, and the tests checked that the
# field existed, never what it said. The relationship is fully determined by
# the two five-element cycles and the two stems' polarity, so it is computed
# from them: same polarity gives the "partial" god of each pair.
_GENERATES: Final[dict[str, str]] = {
    "Wood": "Fire", "Fire": "Earth", "Earth": "Metal", "Metal": "Water", "Water": "Wood",
}
_CONTROLS: Final[dict[str, str]] = {
    "Wood": "Earth", "Earth": "Water", "Water": "Fire", "Fire": "Metal", "Metal": "Wood",
}


def _ten_god(day_master: str, stem: str) -> str:
    """Ten God of `stem` (English name) as seen from the `day_master` stem."""
    own, other = ELEMENTS[day_master], ELEMENTS[stem]
    same = STEM_POLARITY[day_master] == STEM_POLARITY[stem]
    if other == own:
        return "Bi Jian" if same else "Rob Wealth"
    if _GENERATES[own] == other:  # what the Day Master produces: output
        return "Food God" if same else "Injured Officer"
    if _CONTROLS[own] == other:  # what it controls: wealth
        return "Indirect Wealth" if same else "Direct Wealth"
    if _CONTROLS[other] == own:  # what controls it: officer
        return "Seven Killings" if same else "Direct Officer"
    return "Partial Seal" if same else "Direct Seal"  # what produces it: resource


TEN_GODS: Final[list[list[str]]] = [
    [_ten_god(day_master, stem) for stem in HEAVENLY_STEMS_ENGLISH]
    for day_master in HEAVENLY_STEMS_ENGLISH
]


TEN_GOD_PL: Final[dict[str, str]] = {
    "Bi Jian": "Równy Brat (Bi Jian)",
    "Rob Wealth": "Grabieżca Bogactwa (Jie Cai)",
    "Food God": "Bóg Jedzenia (Shi Shen)",
    "Injured Officer": "Ranny Urzędnik (Shang Guan)",
    "Indirect Wealth": "Niebezpośrednie Bogactwo (Pian Cai)",
    "Direct Wealth": "Bezpośrednie Bogactwo (Zheng Cai)",
    "Partial Seal": "Częściowa Pieczęć (Pian Yin)",
    "Direct Seal": "Bezpośrednia Pieczęć (Zheng Yin)",
    "Seven Killings": "Siedem Zabójców (Qi Sha)",
    "Direct Officer": "Bezpośredni Urzędnik (Zheng Guan)",
}


def _stem_info(char: str) -> dict:
    """Return English name, polarity and element for a heavenly-stem hanzi."""
    index = HEAVENLY_STEMS_HANZI.index(char)
    english = HEAVENLY_STEMS_ENGLISH[index]
    return {
        "hanzi": char,
        "english": english,
        "polarity": STEM_POLARITY[english],
        "element": ELEMENTS[english],
    }


def _branch_info(char: str) -> dict:
    """Return animal, element and polarity for an earthly-branch hanzi."""
    # Branch polarity alternates starting with Yang for 子 (Rat).
    branch_index = list(ZODIAC_ANIMALS.keys()).index(char)
    polarity = "Yang" if branch_index % 2 == 0 else "Yin"
    return {
        "hanzi": char,
        "animal": ZODIAC_ANIMALS.get(char, "Unknown"),
        "element": BRANCH_ELEMENTS.get(char, "Unknown"),
        "polarity": polarity,
    }


def _ten_gods_for_pillar(
    day_master_hanzi: str, pillar_stem: str, pillar_branch: str
) -> dict:
    """Return the Ten Gods relationships for a pillar relative to Day Master."""
    dm_index = HEAVENLY_STEMS_HANZI.index(day_master_hanzi)

    stem_index = HEAVENLY_STEMS_HANZI.index(pillar_stem)
    stem_god = TEN_GODS[dm_index][stem_index]

    hidden_gods = []
    for hidden_stem in HIDDEN_STEMS.get(pillar_branch, ()):
        hidden_index = HEAVENLY_STEMS_HANZI.index(hidden_stem)
        hidden_gods.append({
            "stem": _stem_info(hidden_stem),
            "ten_god": TEN_GOD_PL[TEN_GODS[dm_index][hidden_index]],
        })

    return {
        "stem_ten_god": TEN_GOD_PL[stem_god],
        "hidden_stems_ten_gods": hidden_gods,
    }


def _pillar_info(pillar_hanzi: str, day_master_hanzi: str = "") -> dict:
    """Build a full pillar dictionary from a two-character Hanzi string."""
    stem_char = pillar_hanzi[0]
    branch_char = pillar_hanzi[1]
    pillar = {
        "hanzi": pillar_hanzi,
        "stem": _stem_info(stem_char),
        "branch": _branch_info(branch_char),
    }
    if day_master_hanzi:
        pillar["ten_gods"] = _ten_gods_for_pillar(
            day_master_hanzi, stem_char, branch_char
        )
    return pillar


def _element_count(pillars: list[dict]) -> dict:
    """Count the five elements across visible stems and branches.

    Hidden stems are deliberately excluded from the simple count; the prompt
    can use the detailed hidden-stem data for deeper analysis.
    """
    counts: dict[str, int] = {"Wood": 0, "Fire": 0, "Earth": 0, "Metal": 0, "Water": 0}
    for pillar in pillars:
        counts[pillar["stem"]["element"]] += 1
        counts[pillar["branch"]["element"]] += 1
    return counts


def _next_stem(stem_hanzi: str) -> str:
    """Return the next heavenly stem in the 10-stem cycle."""
    idx = HEAVENLY_STEMS_HANZI.index(stem_hanzi)
    return HEAVENLY_STEMS_HANZI[(idx + 1) % 10]


def _prev_stem(stem_hanzi: str) -> str:
    """Return the previous heavenly stem in the 10-stem cycle."""
    idx = HEAVENLY_STEMS_HANZI.index(stem_hanzi)
    return HEAVENLY_STEMS_HANZI[(idx - 1) % 10]


def _next_branch(branch_hanzi: str) -> str:
    """Return the next earthly branch in the 12-branch cycle."""
    branches = list(ZODIAC_ANIMALS.keys())
    idx = branches.index(branch_hanzi)
    return branches[(idx + 1) % 12]


def _prev_branch(branch_hanzi: str) -> str:
    """Return the previous earthly branch in the 12-branch cycle."""
    branches = list(ZODIAC_ANIMALS.keys())
    idx = branches.index(branch_hanzi)
    return branches[(idx - 1) % 12]


def _year_stem_is_yang(year_stem_english: str) -> bool:
    """Return True if the year's heavenly stem is Yang."""
    return STEM_POLARITY.get(year_stem_english) == "Yang"


def _da_yun_direction(year_stem_english: str, gender: str | None) -> tuple[str, bool]:
    """Return (direction, is_assumed) for Da Yun progression.

    Rules:
      * Male + Yang year, or Female + Yin year  -> forward.
      * Male + Yin year, or Female + Yang year  -> backward.
      * Gender unknown -> forward (assumed).
    """
    year_yang = _year_stem_is_yang(year_stem_english)
    if gender == "male":
        return ("forward", False) if year_yang else ("backward", False)
    if gender == "female":
        return ("backward", False) if year_yang else ("forward", False)
    return "forward", True


def _sun_longitude(jd_ut: float) -> float:
    result, err = swe.calc_ut(jd_ut, swe.SUN, 0)
    if err and not result:
        raise RuntimeError(f"Failed to compute Sun position: {err}")
    return float(result[0]) % 360.0


def _jie_julian_day(jd_ut: float, forward: bool) -> float:
    """Julian Day UT of the nearest month-opening solar term (Jie) after or before jd_ut.

    The twelve Jie that open the BaZi months (Li Chun 315°, Jing Zhe 345°,
    Qing Ming 15°, ... Xiao Han 285°) sit at Sun longitudes of 15° + 30°k.
    """
    longitude = _sun_longitude(jd_ut)
    offset = (longitude - 15.0) % 30.0
    target = (longitude + (30.0 - offset if forward else -offset)) % 360.0
    jd = jd_ut + (30.0 - offset if forward else -offset) / 0.9856
    for _ in range(20):
        delta = (_sun_longitude(jd) - target + 180.0) % 360.0 - 180.0
        if abs(delta) < 1e-6:
            break
        jd -= delta / 0.9856
    return jd


#: Sun longitude of Li Chun (立春), the solar term that opens the BaZi year.
LI_CHUN_LONGITUDE: Final[float] = 315.0


def li_chun_julian_day(year: int) -> float:
    """Julian Day UT of Li Chun in Gregorian `year`: the Sun at 315° (3-5 February)."""
    jd = swe.julday(year, 2, 4, 12.0)
    for _ in range(30):
        delta = (_sun_longitude(jd) - LI_CHUN_LONGITUDE + 180.0) % 360.0 - 180.0
        if abs(delta) < 1e-7:  # ~0.01 s of the Sun's motion
            break
        jd -= delta / 0.9856
    return jd


def bazi_month_index(julian_day_ut: float) -> int:
    """BaZi month in force at a moment in UT: 0 = 寅 (from Li Chun, 315°) ... 11 = 丑.

    Each month opens at its Jie, the Sun at 315° + 30°k, to the moment.
    """
    return int(((_sun_longitude(julian_day_ut) - LI_CHUN_LONGITUDE) % 360.0) // 30.0)


def bazi_year(julian_day_ut: float) -> int:
    """Gregorian year whose Li Chun opened the BaZi year in force at `julian_day_ut`.

    Read from the same Sun longitude as the month, so the year and the month
    can never disagree: in January and February the 子 and 丑 months (k 10, 11)
    still belong to the previous year.
    """
    year, month = swe.revjul(julian_day_ut)[:2]
    return year - 1 if month <= 2 and bazi_month_index(julian_day_ut) >= 10 else year


def year_pillar_hanzi(julian_day_ut: float) -> str:
    """Year pillar (two hanzi) in force at a moment in UT, changing at Li Chun.

    Not at the Chinese New Year: cnlunar's `year8Char` changes with the lunar
    year, which put the year pillar out of step with the month pillar for
    births between Li Chun and the New Year (6 Feb 2013 came out 壬辰 with a
    甲寅 month instead of 癸巳; 28 Jan 2023 癸卯 with a 癸丑 month instead of
    壬寅). Fixed in ENGINE_VERSION 1.0.7.
    """
    cycle = bazi_year(julian_day_ut) - 4  # 4 CE was a 甲子 year
    return HEAVENLY_STEMS_HANZI[cycle % 10] + list(ZODIAC_ANIMALS)[cycle % 12]


def month_pillar_hanzi(julian_day_ut: float) -> str:
    """Month pillar (two hanzi) in force at a moment in UT, changing at its Jie.

    The branch from the Sun (寅 from Li Chun, 卯 from Jing Zhe, ...), the stem by
    五虎遁 from the year stem: 甲己 years open with 丙寅, 乙庚 with 戊寅, 丙辛
    with 庚寅, 丁壬 with 壬寅, 戊癸 with 甲寅. Until 1.0.8 the month came from
    cnlunar, which opens it at local midnight of the Beijing date of the Jie:
    for births in Poland up to ~18 hours early or ~7 hours late, about 1% of
    all births (owner's report, 2026-11-17).
    """
    k = bazi_month_index(julian_day_ut)
    year_stem = (bazi_year(julian_day_ut) - 4) % 10
    stem = (year_stem % 5 * 2 + 2 + k) % 10
    return HEAVENLY_STEMS_HANZI[stem] + list(ZODIAC_ANIMALS)[(2 + k) % 12]


def four_pillars(local: datetime, julian_day_ut: float) -> tuple[str, str, str, str]:
    """(year, month, day, hour) pillars for a birth moment, as hanzi pairs.

    The one place the pillars come from, for `compute_bazi` and for the
    whole-day variants (`day_variants`). The year and the month follow the
    Sun to the moment in UT (Li Chun and the other Jie, Swiss Ephemeris); the
    day and the hour come from cnlunar on the local wall clock to the minute
    (the day changing at 23:00 local, the owner's decision of 2026-11-10).
    """
    lunar = cnlunar.Lunar(
        datetime(local.year, local.month, local.day, local.hour, local.minute), godType="8char"
    )
    return (
        year_pillar_hanzi(julian_day_ut),
        month_pillar_hanzi(julian_day_ut),
        lunar.day8Char,
        lunar.twohour8Char,
    )


def _na_yin(day_pillar_hanzi: str) -> str:
    """Na Yin of the day pillar, as cnlunar's `get_nayin` gives it."""
    return theHalf60HeavenlyEarth5ElementsList[the60HeavenlyEarth.index(day_pillar_hanzi) // 2]


def _start_age_from_jie(jd_ut: float, forward: bool) -> float:
    """Da Yun starting age in years: days to the next Jie (forward) or since the
    previous one (backward), at the classical three days to one year."""
    return abs(_jie_julian_day(jd_ut, forward) - jd_ut) / 3.0


_DAYS_PER_YEAR: Final[float] = 365.2425


def _da_yun_calendar(pillars: list[dict], birth_date: date, start_age: float, reference_date: date) -> None:
    """Add `start_year`, `end_year` and `is_current` to each pillar, in place.

    The pillars change at birth + start age + 10k years, so the years come
    from the precise starting age, not the rounded one. Without them the
    synthesis turned "ages 28-37" into "you are entering it now, at 33" in
    about 25 places per report (2026-11-02).
    """
    for index, pillar in enumerate(pillars):
        start = birth_date + timedelta(days=(start_age + index * 10) * _DAYS_PER_YEAR)
        end = birth_date + timedelta(days=(start_age + (index + 1) * 10) * _DAYS_PER_YEAR)
        pillar["start_year"] = start.year
        pillar["end_year"] = end.year
        pillar["is_current"] = start <= reference_date < end


def _compute_da_yun(
    month_pillar_hanzi: str,
    year_stem_english: str,
    day_master_hanzi: str,
    gender: str | None,
    birth_day: int,
    julian_day_ut: float | None = None,
) -> dict:
    """Compute the 10-year Great Luck Pillars (Da Yun) from the month pillar.

      * 8 pillars, each spanning 10 years. The first one is the pillar next to
        the month pillar in the direction of travel, never the month pillar
        itself (until 2026-10-29 it was, which shifted every decade by one).
      * Starting age comes from the distance to the nearest Jie solar term when
        `julian_day_ut` is given; otherwise a 3/4-year heuristic, flagged
        approximate.
      * Direction follows the standard gender/year-stem rule.
    """
    direction, is_assumed = _da_yun_direction(year_stem_english, gender)
    forward = direction == "forward"
    step_stem = _next_stem if forward else _prev_stem
    step_branch = _next_branch if forward else _prev_branch

    current_stem = month_pillar_hanzi[0]
    current_branch = month_pillar_hanzi[1]

    if julian_day_ut is not None:
        start_age_precise: float | None = round(_start_age_from_jie(julian_day_ut, forward), 2)
        start_age = math.floor(start_age_precise + 0.5)
        approximate = False
    else:
        start_age_precise = None
        start_age = 3 if birth_day <= 15 else 4
        approximate = True

    pillars: list[dict] = []
    for i in range(8):
        current_stem = step_stem(current_stem)
        current_branch = step_branch(current_branch)
        pillar_hanzi = current_stem + current_branch
        pillar = _pillar_info(pillar_hanzi, day_master_hanzi)
        pillar["start_age"] = start_age + i * 10
        pillar["end_age"] = start_age + (i + 1) * 10 - 1
        pillars.append(pillar)

    return {
        "pillars": pillars,
        "direction": direction,
        "direction_assumed": is_assumed,
        "start_age": start_age,
        "start_age_precise": start_age_precise,
        "start_age_approximate": approximate,
    }


def _useful_god(element_count: dict, day_master_element: str) -> dict:
    """Return a simplified Useful God recommendation.

    This is a deterministic heuristic, not a full BaZi consult:
    * weak Day Master -> supports it (same element or producing element),
    * strong Day Master -> drains or controls it.
    """
    producing = {
        "Wood": "Water",
        "Fire": "Wood",
        "Earth": "Fire",
        "Metal": "Earth",
        "Water": "Metal",
    }
    same = day_master_element

    total = sum(element_count.values())
    dm_score = element_count.get(day_master_element, 0)
    production_score = element_count.get(producing[day_master_element], 0)

    if dm_score + production_score < total / 2.0:
        strength = "weak"
        useful_element = producing[day_master_element]
    else:
        strength = "strong"
        draining = {
            "Wood": "Fire",
            "Fire": "Earth",
            "Earth": "Metal",
            "Metal": "Water",
            "Water": "Wood",
        }
        useful_element = draining[day_master_element]

    return {
        "day_master_strength": strength,
        "useful_element": useful_element,
        "rationale": (
            f"Day Master {day_master_element} is {strength}; "
            f"{useful_element} balances the chart."
        ),
    }


def compute_bazi(
    birth_date: date,
    birth_time: time,
    gender: str | None = None,
    julian_day_ut: float | None = None,
    reference_date: date | None = None,
) -> dict:
    """Compute the full Four Pillars BaZi reading for a birth moment.

    Args:
        birth_date: Local birth date.
        birth_time: Local birth time.
        gender: Optional biological gender ('male' or 'female') used to pick
            the correct Da Yun direction. If omitted, forward direction is
            assumed and the response flags this.
        julian_day_ut: Birth moment in UT. It places the birth against Li
            Chun and the other Jie, which open the year and month pillars,
            and gives the Da Yun starting age from the solar terms. Without
            it the local wall clock is read as UT: the year and month pillars
            can then be wrong only for a birth within the time-zone offset
            (at most 14 hours) of a Jie, and the Da Yun starting age falls
            back to an approximation (flagged).
            Every engine caller (`compute_profile`) passes it.
        reference_date: Date the current Da Yun pillar (`is_current`) is
            reported for. Defaults to today (UTC).

    Returns:
        Dictionary with all four pillars, Day Master, and Da Yun timeline.
    """
    dt = datetime(
        year=birth_date.year,
        month=birth_date.month,
        day=birth_date.day,
        hour=birth_time.hour,
        minute=birth_time.minute,
    )
    if julian_day_ut is None:
        moment_jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0)
    else:
        moment_jd = julian_day_ut
    year_hanzi, month_hanzi, day_hanzi, hour_hanzi = four_pillars(dt, moment_jd)

    day_master_hanzi = day_hanzi[0]
    year_pillar = _pillar_info(year_hanzi, day_master_hanzi)
    month_pillar = _pillar_info(month_hanzi, day_master_hanzi)
    day_pillar = _pillar_info(day_hanzi, day_master_hanzi)
    hour_pillar = _pillar_info(hour_hanzi, day_master_hanzi)

    pillars = [year_pillar, month_pillar, day_pillar, hour_pillar]
    element_count = _element_count(pillars)
    day_master = _stem_info(day_master_hanzi)
    useful_god = _useful_god(element_count, day_master["element"])

    da_yun = _compute_da_yun(
        month_pillar_hanzi=month_hanzi,
        year_stem_english=year_pillar["stem"]["english"],
        day_master_hanzi=day_master_hanzi,
        gender=gender,
        birth_day=birth_date.day,
        julian_day_ut=julian_day_ut,
    )
    precise_age = da_yun["start_age_precise"]
    _da_yun_calendar(
        da_yun["pillars"],
        birth_date,
        precise_age if precise_age is not None else da_yun["start_age"],
        resolve_reference_date(reference_date),
    )

    return {
        "year_pillar": year_pillar,
        "month_pillar": month_pillar,
        "day_pillar": day_pillar,
        "hour_pillar": hour_pillar,
        "day_master": day_master,
        "element_count": element_count,
        "useful_god": useful_god,
        "na_yin": _na_yin(day_hanzi),
        "da_yun": da_yun["pillars"],
        "da_yun_direction": da_yun["direction"],
        "da_yun_direction_assumed": da_yun["direction_assumed"],
        "da_yun_start_age": da_yun["start_age"],
        "da_yun_start_age_precise": da_yun["start_age_precise"],
        "da_yun_start_age_approximate": da_yun["start_age_approximate"],
    }
