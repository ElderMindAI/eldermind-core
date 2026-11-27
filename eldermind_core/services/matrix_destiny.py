"""Matrix of Destiny (Matryca Losu) calculation module.

The system operates on the numbers 1-22. Any intermediate result greater
than 22 is reduced by summing its digits until the value is <= 22.
Zero is not a valid value in this system.
"""

import calendar
from datetime import date
from typing import Final

from eldermind_core.core.reference import resolve_reference_date


_MATRIX_MIN = 1
_MATRIX_MAX = 22

# Standard Tarot arcana names used by the Matrix of Destiny (1-22).
# 22 is traditionally the Fool / Głupiec in this system.
TAROT_ARCANA: Final[dict[int, str]] = {
    1: "Mag",
    2: "Kapłanka",
    3: "Cesarzowa",
    4: "Cesarz",
    5: "Hierofant",
    6: "Kochankowie",
    7: "Rydwan",
    8: "Siła",
    9: "Pustelnik",
    10: "Koło Fortuny",
    11: "Sprawiedliwość",
    12: "Wisielec",
    13: "Śmierć",
    14: "Umiar",
    15: "Diabeł",
    16: "Wieża",
    17: "Gwiazda",
    18: "Księżyc",
    19: "Słońce",
    20: "Sąd Ostateczny",
    21: "Świat",
    22: "Głupiec",
}

# Decades reported in `timeline` — the keys callers have always read. Since
# 1.1.0 each one is the octagram vertex the age ring reaches at that age
# (20 top, 30 top-right, 40 right, 50 bottom-right, 60 bottom). Up to 1.0.8 they
# were mapped right/bottom/left/center/top, which matches no standard chart.
_TIMELINE_DECADES: Final[tuple[int, ...]] = (20, 30, 40, 50, 60)


def _reduce_to_matrix_range(value: int) -> int:
    """Reduce a number to the Matrix of Destiny range [1, 22].

    Values above 22 are reduced by repeated digit summing. Values below 1
    are undefined in this system and raise an error.
    """
    if value < _MATRIX_MIN:
        raise ValueError(f"Matrix of Destiny does not support values below {_MATRIX_MIN}")

    while value > _MATRIX_MAX:
        value = sum(int(digit) for digit in str(value))

    return value


def _sum_digits(value: int) -> int:
    """Sum all decimal digits of an integer."""
    return sum(int(digit) for digit in str(abs(value)))


def compute_matrix_of_destiny(
    birth_date: date,
    reference_date: date | None = None,
) -> dict:
    """Calculate the advanced Matrix of Destiny chart.

    Args:
        birth_date: The subject's birth date (day, month, year).
        reference_date: Date used to compute the current age and highlight the
            active decade. Defaults to today (UTC). Everything else in the chart
            is time-invariant.

    Returns:
        Dictionary with core vertices, derived lines and personal destiny.

    Vertex meanings:
        top    (A) - Talent / Crown
        left   (B) - Portrait / External karma
        right  (C) - Goal / Money entry
        bottom (D) - Karmic tail / Weakness
        center (E) - Comfort zone / Core
    """
    month = birth_date.month
    day = birth_date.day
    year = birth_date.year

    top = _reduce_to_matrix_range(month)
    left = _reduce_to_matrix_range(day)
    right = _reduce_to_matrix_range(_sum_digits(year))
    bottom = _reduce_to_matrix_range(top + left + right)
    center = _reduce_to_matrix_range(top + left + right + bottom)

    # Intermediate points between center and outer vertices.
    center_top = _reduce_to_matrix_range(center + top)
    center_left = _reduce_to_matrix_range(center + left)
    center_right = _reduce_to_matrix_range(center + right)
    center_bottom = _reduce_to_matrix_range(center + bottom)

    # Derived line sequences (each read from outer vertex toward the base).
    wealth = [right, center_right, _reduce_to_matrix_range(right + center_right)]
    # Deprecated in 1.1.0: summed the wrong points (right+bottom, center-right +
    # center-bottom, bottom + center-bottom). The standard love line is
    # `love_money`. Kept unchanged so existing callers do not break.
    relationship = [
        _reduce_to_matrix_range(right + bottom),
        _reduce_to_matrix_range(center_right + center_bottom),
        _reduce_to_matrix_range(bottom + center_bottom),
    ]
    karmic_tail = [
        bottom,
        center_bottom,
        _reduce_to_matrix_range(bottom + center_bottom),
    ]

    # Personal Destiny up to 40 years: diagonal (top+bottom) + horizontal (left+right).
    diagonal = _reduce_to_matrix_range(top + bottom)
    horizontal = _reduce_to_matrix_range(left + right)
    personal_destiny_40 = _reduce_to_matrix_range(diagonal + horizontal)

    core = {
        "top": top,
        "left": left,
        "right": right,
        "bottom": bottom,
        "center": center,
    }

    arcana_names = {key: TAROT_ARCANA[value] for key, value in core.items()}

    octagram = _compute_octagram(core)
    ring = _compute_age_ring(octagram, birth_date)
    current, following, age_exact = _locate_on_ring(
        ring, birth_date, resolve_reference_date(reference_date)
    )

    return {
        "core": core,
        "core_names": arcana_names,
        "intermediate": {
            "center_top": center_top,
            "center_left": center_left,
            "center_right": center_right,
            "center_bottom": center_bottom,
        },
        "lines": {
            "karmic_tail": karmic_tail,
            "wealth": wealth,
            "relationship": relationship,
        },
        "personal_destiny_40": personal_destiny_40,
        "personal_destiny_40_name": TAROT_ARCANA[personal_destiny_40],
        "timeline": _compute_age_timeline(octagram, birth_date, reference_date),
        "octagram": octagram,
        "heart_points": _compute_heart_points(octagram),
        "love_money": _compute_love_money(octagram),
        "age_ring": ring,
        "age_exact": age_exact,
        "current_point": current,
        "next_point": following,
        "deprecated": dict(DEPRECATED_FIELDS),
    }


#: Fields kept for compatibility, with what replaces them. Shipped in the
#: payload so an API client sees the notice next to the data.
DEPRECATED_FIELDS: Final[dict[str, str]] = {
    "lines.relationship": "since engine 1.1.0; use love_money (love, mid, money)",
}


# --- Full octagram (engine 1.1.0) -----------------------------------------
#
# The standard chart: two squares turned 45° to each other. The straight
# square is the old `core` (left = day, top = month, right = year, bottom =
# their sum); each diagonal vertex is the sum of its two neighbours. On every
# one of the 8 rays sit two inner points: `in2` = vertex + center (nearer the
# middle), `in1` = vertex + in2 (next to the vertex).

#: Clockwise from the left vertex — also the order of the age ring, which
#: starts at the left vertex at birth and reaches each next one 10 years on.
OCTAGRAM_ORDER: Final[tuple[str, ...]] = (
    "left",
    "top_left",
    "top",
    "top_right",
    "right",
    "bottom_right",
    "bottom",
    "bottom_left",
)

_RING_STEP_MONTHS: Final[int] = 15  # 1.25 years
_RING_POINTS_PER_SIDE: Final[int] = 8  # the vertex + 7 points before the next one
_RING_YEARS: Final[int] = 80
_DAYS_PER_YEAR: Final[float] = 365.2425


def _arcana(value: int) -> dict:
    return {"value": value, "name": TAROT_ARCANA[value]}


def _compute_octagram(core: dict[str, int]) -> dict:
    r = _reduce_to_matrix_range
    values = {
        "left": core["left"],
        "top_left": r(core["left"] + core["top"]),
        "top": core["top"],
        "top_right": r(core["top"] + core["right"]),
        "right": core["right"],
        "bottom_right": r(core["right"] + core["bottom"]),
        "bottom": core["bottom"],
        "bottom_left": r(core["bottom"] + core["left"]),
    }
    center = core["center"]
    octagram: dict = {}
    for key in OCTAGRAM_ORDER:
        vertex = values[key]
        in2 = r(vertex + center)
        octagram[key] = {**_arcana(vertex), "in1": r(vertex + in2), "in2": in2}
    octagram["center"] = _arcana(center)
    return octagram


def _compute_heart_points(octagram: dict) -> dict[str, int]:
    """The two points between `in2` and the center on the left and top rays."""
    center = octagram["center"]["value"]
    return {
        "left": _reduce_to_matrix_range(octagram["left"]["in2"] + center),
        "top": _reduce_to_matrix_range(octagram["top"]["in2"] + center),
    }


def _compute_love_money(octagram: dict) -> dict[str, int]:
    """The line from `in2` of the bottom ray to `in2` of the right ray.

    `mid` halves it; `love` sits on the bottom side, `money` on the right.
    """
    r = _reduce_to_matrix_range
    bottom = octagram["bottom"]["in2"]
    right = octagram["right"]["in2"]
    mid = r(bottom + right)
    return {"love": r(bottom + mid), "mid": mid, "money": r(right + mid)}


def _side_points(a: int, b: int) -> list[int]:
    """The 7 points between two vertices 10 years apart, by recursive midpoint.

    Returned in age order: +1.25, +2.5, +3.75, +5, +6.25, +7.5, +8.75.
    """
    r = _reduce_to_matrix_range
    p5 = r(a + b)
    p2_5 = r(a + p5)
    p7_5 = r(p5 + b)
    return [r(a + p2_5), p2_5, r(p2_5 + p5), p5, r(p5 + p7_5), p7_5, r(p7_5 + b)]


#: Position on a side (0 = vertex) -> (level, label offsets). Level 0 is the
#: vertex, 1 the 5-year point, 2 the 2.5-year points, 3 the 1.25-year points.
#: Labels follow the reference charts: "1–2" at +1.25, "5" at +5.
_SIDE_SLOTS: Final[tuple[tuple[int, tuple[int, ...]], ...]] = (
    (0, (0,)),
    (3, (1, 2)),
    (2, (2, 3)),
    (3, (3, 4)),
    (1, (5,)),
    (3, (6, 7)),
    (2, (7, 8)),
    (3, (8, 9)),
)


def _add_months(start: date, months: int) -> date:
    """`start` moved by whole months; a day past the month's end is clamped."""
    total = start.month - 1 + months
    year, month = start.year + total // 12, total % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _compute_age_ring(octagram: dict, birth_date: date) -> list[dict]:
    """64 points from birth (0) to just before 80, one every 1.25 years."""
    ring: list[dict] = []
    for side, key in enumerate(OCTAGRAM_ORDER):
        a = octagram[key]["value"]
        b = octagram[OCTAGRAM_ORDER[(side + 1) % len(OCTAGRAM_ORDER)]]["value"]
        arcanas = [a, *_side_points(a, b)]
        decade = side * 10
        for slot, (arcana, (level, offsets)) in enumerate(zip(arcanas, _SIDE_SLOTS)):
            months = (side * _RING_POINTS_PER_SIDE + slot) * _RING_STEP_MONTHS
            start = _add_months(birth_date, months)
            ring.append(
                {
                    "age": months / 12,
                    "label": "–".join(str(decade + o) for o in offsets),
                    "arcana": arcana,
                    "name": TAROT_ARCANA[arcana],
                    "level": level,
                    "start_date": start.isoformat(),
                    "calendar_year": start.year,
                }
            )
    return ring


def _locate_on_ring(
    ring: list[dict], birth_date: date, today: date
) -> tuple[dict | None, dict | None, float]:
    """The ring point whose segment holds `today`, the one after it, exact age.

    A segment runs from its point's start date up to the next point's. Before
    birth there is no current point (the next one is birth itself); from 80
    on, neither — the ring ends there.
    """
    age_exact = round((today - birth_date).days / _DAYS_PER_YEAR, 2)
    index = -1
    for position, point in enumerate(ring):
        if date.fromisoformat(point["start_date"]) <= today:
            index = position
        else:
            break
    if index == len(ring) - 1 and today >= _add_months(birth_date, _RING_YEARS * 12):
        return None, None, age_exact
    current = ring[index] if index >= 0 else None
    following = ring[index + 1] if index + 1 < len(ring) else None
    return current, following, age_exact


def _compute_age_timeline(
    octagram: dict,
    birth_date: date,
    reference_date: date | None = None,
) -> dict:
    """Build the decade timeline and highlight the client's current decade.

    Each decade is the octagram vertex the age ring reaches at its start:
    20s -> top, 30s -> top_right, 40s -> right, 50s -> bottom_right,
    60s -> bottom (the ring opens at the left vertex at birth, 10 years a side).
    """
    today = resolve_reference_date(reference_date)
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    decades = {}
    highlighted_decade = None
    for decade in _TIMELINE_DECADES:
        vertex = OCTAGRAM_ORDER[decade // 10]
        arcana_number = octagram[vertex]["value"]
        decades[str(decade)] = {
            "vertex": vertex,
            "arcana_number": arcana_number,
            "arcana_name": TAROT_ARCANA[arcana_number],
        }
        if decade <= age < decade + 10:
            highlighted_decade = str(decade)

    return {
        "current_age": age,
        "highlighted_decade": highlighted_decade,
        "decades": decades,
    }


def compute_karmic_points(birth_date: date) -> dict:
    """The karmic points of the Matrix (plan „Kundalini i Karma”, session SE).

    Nothing new is calculated: both values are read from
    `compute_matrix_of_destiny`, so they always match the full chart.

    * ``karmic_tail`` — the line ``lines.karmic_tail``: bottom vertex (D),
      center-bottom point, and their sum reduced to 1-22.
    * ``external_karma`` — vertex B (``core.left``, the reduced birth day),
      described in the chart as "Portrait / External karma".

    Returns:
        ``{"karmic_tail": [{"position", "arcana_number", "arcana_name"} x3],
        "external_karma": {"vertex": "B", "arcana_number", "arcana_name"}}``.
    """
    chart = compute_matrix_of_destiny(birth_date)
    positions = ("bottom", "center_bottom", "bottom_plus_center_bottom")
    tail = [
        {"position": position, "arcana_number": number, "arcana_name": TAROT_ARCANA[number]}
        for position, number in zip(positions, chart["lines"]["karmic_tail"])
    ]
    left = chart["core"]["left"]
    return {
        "karmic_tail": tail,
        "external_karma": {"vertex": "B", "arcana_number": left, "arcana_name": TAROT_ARCANA[left]},
    }


def arcana_name(arcana_number: int) -> str:
    """Return the Tarot arcana name for a Matrix number (1-22)."""
    if not _MATRIX_MIN <= arcana_number <= _MATRIX_MAX:
        raise ValueError(f"Arcana number must be between {_MATRIX_MIN} and {_MATRIX_MAX}")
    return TAROT_ARCANA[arcana_number]
