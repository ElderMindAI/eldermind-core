"""Western numerology helpers (Pythagorean system).

Provides Life Path, Personal Year and name-based numbers derived from the full
birth date and full name. Polish diacritics are flattened to their Latin
counterparts before letter-to-number conversion.
"""

import unicodedata
from datetime import date


MASTER_NUMBERS: set[int] = {11, 22, 33}

PYTHAGOREAN_TABLE: dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "O": 6, "P": 7, "Q": 8, "R": 9,
    "S": 1, "T": 2, "U": 3, "V": 4, "W": 5, "X": 6, "Y": 7, "Z": 8,
}

# Y is always treated as a vowel in the Pythagorean name calculations.
VOWELS: set[str] = set("AEIOUY")

# Explicit transliteration for Polish diacritics (requested flattening to Latin).
POLISH_TRANSLIT: dict[str, str] = {
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
    "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
}


def _normalize_name(name: str) -> str:
    """Flatten Polish diacritics and keep only ASCII letters."""
    translated = []
    for char in name:
        translated.append(POLISH_TRANSLIT.get(char, char))
    text = "".join(translated)
    flattened = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return flattened.upper()


def _letter_value(char: str) -> int:
    """Return the Pythagorean value for a single normalized letter."""
    return PYTHAGOREAN_TABLE.get(char, 0)


def _digit_sum(n: int) -> int:
    """Reduce a positive integer by summing its digits repeatedly.

    Master numbers 11, 22 and 33 are preserved rather than reduced further.
    """
    while n > 9 and n not in MASTER_NUMBERS:
        n = sum(int(d) for d in str(n))
    return n


def compute_life_path(birth_date: date) -> int:
    """Calculate the Life Path number from a full birth date.

    Sums all digits of day, month and year, then reduces to a single digit or
    a master number (11, 22, 33).

    Args:
        birth_date: The local birth date.

    Returns:
        Life Path number.
    """
    raw = sum(int(d) for d in birth_date.isoformat().replace("-", ""))
    return _digit_sum(raw)


def compute_personal_year(birth_date: date, current_date: date) -> int:
    """Calculate the Personal Year number for a given reference year.

    Formula: day + month + current_year, reduced to 1-9 or a master number.

    Args:
        birth_date: The local birth date.
        current_date: The reference date (usually today).

    Returns:
        Personal Year number.
    """
    total = birth_date.day + birth_date.month + current_date.year
    return _digit_sum(total)


def compute_day_number(birth_date: date) -> int:
    """Calculate the Day Number (reduced birth day, master numbers preserved)."""
    return _digit_sum(birth_date.day)


def compute_expression_number(full_name: str) -> int:
    """Calculate the Expression Number from all letters of the full name."""
    clean = _normalize_name(full_name)
    return _digit_sum(sum(_letter_value(ch) for ch in clean))


def compute_soul_urge_number(full_name: str) -> int:
    """Calculate the Soul Urge Number from vowels only (Y counts as vowel)."""
    clean = _normalize_name(full_name)
    return _digit_sum(
        sum(_letter_value(ch) for ch in clean if ch in VOWELS)
    )


def compute_personality_number(full_name: str) -> int:
    """Calculate the Personality Number from consonants only."""
    clean = _normalize_name(full_name)
    return _digit_sum(
        sum(_letter_value(ch) for ch in clean if ch not in VOWELS and _letter_value(ch))
    )


def compute_maturity_number(life_path: int, expression_number: int) -> int:
    """Calculate the Maturity Number from Life Path + Expression Number."""
    return _digit_sum(life_path + expression_number)


def compute_numerology(
    birth_date: date,
    current_date: date,
    full_name: str,
) -> dict:
    """Compute the complete Pythagorean numerology profile.

    Args:
        birth_date: The local birth date.
        current_date: The reference date for Personal Year (usually today).
        full_name: Full name used for letter-based calculations.

    Returns:
        Dictionary with all core numerology numbers.
    """
    life_path = compute_life_path(birth_date)
    expression_number = compute_expression_number(full_name)
    return {
        "life_path": life_path,
        "personal_year": compute_personal_year(birth_date, current_date),
        "expression_number": expression_number,
        "soul_urge_number": compute_soul_urge_number(full_name),
        "personality_number": compute_personality_number(full_name),
        "maturity_number": compute_maturity_number(life_path, expression_number),
        "day_number": compute_day_number(birth_date),
    }
