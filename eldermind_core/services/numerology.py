"""Western numerology helpers (Pythagorean system).

Provides Life Path, Personal Year and name-based numbers derived from the full
birth date and full name. Polish diacritics are flattened to their Latin
counterparts before letter-to-number conversion.
"""

import unicodedata
from datetime import date

from eldermind_core.core.reference import resolve_reference_date


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


# ---------------------------------------------------------------------------
# Karmic indicators (plan „Kundalini i Karma”, session SE, definitions agreed
# with the owner on 2026-11-19). They are separate functions on purpose: the
# existing `compute_numerology` output does not change.
# ---------------------------------------------------------------------------

#: Karmic debt numbers (13/4, 14/5, 16/7, 19/1).
KARMIC_DEBT_NUMBERS: frozenset[int] = frozenset({13, 14, 16, 19})


def reduction_chain(raw: int) -> list[int]:
    """Every stage of the engine's reduction, from the raw sum to the result.

    Uses exactly the rule of `_digit_sum`: digits are summed until the value
    is 1-9 or a master number (11, 22, 33), so the last element always equals
    `_digit_sum(raw)`. Examples: ``31 -> [31, 4]``, ``169 -> [169, 16, 7]``,
    ``199 -> [199, 19, 10, 1]``, ``29 -> [29, 11]``.
    """
    chain = [raw]
    while raw > 9 and raw not in MASTER_NUMBERS:
        raw = sum(int(d) for d in str(raw))
        chain.append(raw)
    return chain


def _debts_in_chain(chain: list[int]) -> list[int]:
    """Karmic debt numbers found at any stage before the final value.

    Definition (owner, 2026-11-19): a number carries a karmic debt when 13,
    14, 16 or 19 appears at **any** stage of its reduction chain except the
    final one — ``169 -> 16 -> 7`` is debt 16, ``199 -> 19 -> 10 -> 1`` is
    debt 19. A master number stops the reduction, so nothing after it is
    looked for. Order of first appearance, no duplicates.
    """
    found: list[int] = []
    for value in chain[:-1]:
        if value in KARMIC_DEBT_NUMBERS and value not in found:
            found.append(value)
    return found


def _chain_entry(raw: int) -> dict:
    chain = reduction_chain(raw)
    return {"value": chain[-1], "chain": chain, "debts": _debts_in_chain(chain)}


def _name_sums(full_name: str) -> tuple[int, int, int]:
    """Raw letter sums (all letters, vowels, consonants) of a normalized name.

    The same letters and the same vowel rule (Y is a vowel) as
    `compute_expression_number`, `compute_soul_urge_number` and
    `compute_personality_number`, so the reduced values always match them.
    """
    clean = _normalize_name(full_name)
    total = sum(_letter_value(ch) for ch in clean)
    vowels = sum(_letter_value(ch) for ch in clean if ch in VOWELS)
    return total, vowels, total - vowels


def compute_karmic_debts(birth_date: date, full_name: str | None = None) -> dict:
    """Karmic debt numbers 13, 14, 16 and 19 in the core numbers.

    Definitions agreed with the owner on 2026-11-19:

    * **Life Path, engine method** (``life_path``): all digits of the date
      summed at once, as `compute_life_path` does; the chain ends in the same
      Life Path number the engine reports elsewhere.
    * **Life Path, classic method** (``life_path_classic``): day, month and
      year (sum of the year's digits) each reduced first (master numbers kept),
      then added and reduced. Returned separately and labelled, because its
      final value can differ from the engine's Life Path (1940-01-07: engine
      22, classic 13 -> 4). The operator confirms by reading which one works.
    * **Birth day** (``birth_day``): the day of the month itself is 13, 14, 16
      or 19.
    * **Expression, Soul Urge, Personality** (from the full birth name): the
      raw letter sum (all letters / vowels with Y / consonants) reduced.
    * In every chain the debt is looked for at any stage except the final
      value (see `_debts_in_chain`).

    Args:
        birth_date: The local birth date.
        full_name: Full name from birth. Optional; without it the three name
            numbers are ``None``.

    Returns:
        ``{"life_path", "life_path_classic", "birth_day", "expression",
        "soul_urge", "personality", "all"}``. Each number is ``{"value",
        "chain", "debts"}`` (the classic Life Path also has ``components``);
        ``all`` lists every debt found in any number, ascending.
    """
    life_raw = sum(int(d) for d in birth_date.isoformat().replace("-", ""))
    life_path = _chain_entry(life_raw)

    components = {
        "day": _digit_sum(birth_date.day),
        "month": _digit_sum(birth_date.month),
        "year": _digit_sum(sum(int(d) for d in str(birth_date.year))),
    }
    life_path_classic = {"components": components, **_chain_entry(sum(components.values()))}

    day = birth_date.day
    birth_day = {
        "value": day,
        "debts": [day] if day in KARMIC_DEBT_NUMBERS else [],
    }

    expression = soul_urge = personality = None
    if full_name and full_name.strip():
        total, vowels, consonants = _name_sums(full_name)
        expression = _chain_entry(total) if total else None
        soul_urge = _chain_entry(vowels) if vowels else None
        personality = _chain_entry(consonants) if consonants else None

    entries = [life_path, life_path_classic, birth_day, expression, soul_urge, personality]
    found = sorted({d for entry in entries if entry for d in entry["debts"]})

    return {
        "life_path": life_path,
        "life_path_classic": life_path_classic,
        "birth_day": birth_day,
        "expression": expression,
        "soul_urge": soul_urge,
        "personality": personality,
        "all": found,
    }


def compute_karmic_lessons(full_name: str | None) -> dict | None:
    """Karmic lessons: digits 1-9 absent from the full birth name.

    Definition agreed with the owner on 2026-11-19: every letter of every
    given name and the birth surname counts (diacritics flattened as in the
    rest of this module, Y = 7). A digit with no letter is a karmic lesson.
    ``counts`` is the inclusion table: how many letters carry each digit.

    Returns:
        ``{"missing": [...], "counts": {"1": n, ..., "9": n}}``, or ``None``
        when no name (or no Latin letter) was supplied.
    """
    if not (full_name and full_name.strip()):
        return None
    values = [_letter_value(ch) for ch in _normalize_name(full_name)]
    values = [v for v in values if v]
    if not values:
        return None
    counts = {str(k): values.count(k) for k in range(1, 10)}
    return {
        "missing": [k for k in range(1, 10) if counts[str(k)] == 0],
        "counts": counts,
    }


def compute_numerology(
    birth_date: date,
    current_date: date | None = None,
    full_name: str | None = None,
) -> dict:
    """Compute the complete Pythagorean numerology profile.

    Args:
        birth_date: The local birth date.
        current_date: The reference date for Personal Year. Defaults to today
            (UTC) — see `eldermind_core.core.reference`.
        full_name: Full name used for letter-based calculations. Optional
            (bloker B2): four of the seven numbers come from the date alone, and
            a caller who does not need name numerology should not have to hand
            over a person's name to get them.

    Returns:
        Dictionary with all core numerology numbers. The four name-derived
        numbers are ``None`` when no name was supplied — absent rather than
        zero, so a consumer cannot mistake "not calculated" for a real value.
    """
    current_date = resolve_reference_date(current_date)
    life_path = compute_life_path(birth_date)

    has_name = bool(full_name and full_name.strip())
    expression_number = compute_expression_number(full_name) if has_name else None

    return {
        "life_path": life_path,
        "personal_year": compute_personal_year(birth_date, current_date),
        "expression_number": expression_number,
        "soul_urge_number": compute_soul_urge_number(full_name) if has_name else None,
        "personality_number": compute_personality_number(full_name) if has_name else None,
        "maturity_number": (
            compute_maturity_number(life_path, expression_number)
            if expression_number is not None
            else None
        ),
        "day_number": compute_day_number(birth_date),
    }
