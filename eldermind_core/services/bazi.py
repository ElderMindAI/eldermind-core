"""BaZi (Four Pillars of Destiny) MVP module.

Provides a minimal BaZi reading using the ``cnlunar`` package:
- Heavenly Stem and Earthly Branch of the day pillar (Day Master).
- Earthly Branch / zodiac animal of the year pillar.
"""

from datetime import date, datetime, time
from typing import Final

import cnlunar

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


def _compute_da_yun(
    month_pillar_hanzi: str,
    year_stem_english: str,
    day_master_hanzi: str,
    gender: str | None,
    birth_day: int,
) -> dict:
    """Compute the 10-year Great Luck Pillars (Da Yun) from the month pillar.

    This is an MVP implementation:
      * 8 pillars are generated, each spanning 10 years.
      * Starting age is approximated to 3 years (precise JieQi-based age would
        require solar-term ephemeris calculations).
      * Direction follows the standard gender/year-stem rule.
    """
    direction, is_assumed = _da_yun_direction(year_stem_english, gender)
    step_stem = _next_stem if direction == "forward" else _prev_stem
    step_branch = _next_branch if direction == "forward" else _prev_branch

    current_stem = month_pillar_hanzi[0]
    current_branch = month_pillar_hanzi[1]

    # Approximate starting age: 3 years, nudged to 4 if born late in the lunar
    # month as a coarse heuristic. JieQi-based calculation is out of MVP scope.
    start_age = 3 if birth_day <= 15 else 4

    pillars: list[dict] = []
    for i in range(8):
        if i > 0:
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
        "start_age_approximate": True,
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
) -> dict:
    """Compute the full Four Pillars BaZi reading for a birth moment.

    Args:
        birth_date: Local birth date.
        birth_time: Local birth time.
        gender: Optional biological gender ('male' or 'female') used to pick
            the correct Da Yun direction. If omitted, forward direction is
            assumed and the response flags this.

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
    lunar = cnlunar.Lunar(dt, godType="8char")

    day_master_hanzi = lunar.day8Char[0]
    year_pillar = _pillar_info(lunar.year8Char, day_master_hanzi)
    month_pillar = _pillar_info(lunar.month8Char, day_master_hanzi)
    day_pillar = _pillar_info(lunar.day8Char, day_master_hanzi)
    hour_pillar = _pillar_info(lunar.twohour8Char, day_master_hanzi)

    pillars = [year_pillar, month_pillar, day_pillar, hour_pillar]
    element_count = _element_count(pillars)
    day_master = _stem_info(day_master_hanzi)
    useful_god = _useful_god(element_count, day_master["element"])

    da_yun = _compute_da_yun(
        month_pillar_hanzi=lunar.month8Char,
        year_stem_english=year_pillar["stem"]["english"],
        day_master_hanzi=day_master_hanzi,
        gender=gender,
        birth_day=birth_date.day,
    )

    return {
        "year_pillar": year_pillar,
        "month_pillar": month_pillar,
        "day_pillar": day_pillar,
        "hour_pillar": hour_pillar,
        "day_master": day_master,
        "element_count": element_count,
        "useful_god": useful_god,
        "na_yin": lunar.get_nayin(),
        "da_yun": da_yun["pillars"],
        "da_yun_direction": da_yun["direction"],
        "da_yun_direction_assumed": da_yun["direction_assumed"],
        "da_yun_start_age": da_yun["start_age"],
    }
