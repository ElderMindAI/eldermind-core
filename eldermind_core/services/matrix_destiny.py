"""Matrix of Destiny (Matryca Losu) calculation module.

The system operates on the numbers 1-22. Any intermediate result greater
than 22 is reduced by summing its digits until the value is <= 22.
Zero is not a valid value in this system.
"""

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

# Age-to-vertex mapping for the Matrix life timeline.
# Each decade is governed by one of the five core vertices.
_AGE_VERTEX_ORDER: Final[list[str]] = [
    "right",    # 20s
    "bottom",   # 30s
    "left",     # 40s
    "center",   # 50s
    "top",      # 60s
]


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
        "timeline": _compute_age_timeline(core, birth_date, reference_date),
    }


def _compute_age_timeline(
    core: dict[str, int],
    birth_date: date,
    reference_date: date | None = None,
) -> dict:
    """Build the decade timeline and highlight the client's current decade.

    The Matrix maps each decade of adult life to one of the core vertices:
    20s -> right, 30s -> bottom, 40s -> left, 50s -> center, 60s -> top.
    """
    today = resolve_reference_date(reference_date)
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    decades = {}
    highlighted_decade = None
    for index, vertex in enumerate(_AGE_VERTEX_ORDER, start=2):
        decade = index * 10
        arcana_number = core[vertex]
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


def arcana_name(arcana_number: int) -> str:
    """Return the Tarot arcana name for a Matrix number (1-22)."""
    if not _MATRIX_MIN <= arcana_number <= _MATRIX_MAX:
        raise ValueError(f"Arcana number must be between {_MATRIX_MIN} and {_MATRIX_MAX}")
    return TAROT_ARCANA[arcana_number]
