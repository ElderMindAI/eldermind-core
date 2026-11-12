"""Decan of an ecliptic longitude and its Golden Dawn tarot card.

Pure table lookup on a tropical longitude: no ephemeris call, no randomness.
Positions come from `ephemeris.compute_all_planets` / `compute_houses` (the
`longitude` field); this module only says which of the 36 ten-degree slices a
longitude falls in and what the tradition attaches to that slice.

Two schools of decan rulers are returned side by side:

* `ruler_chaldean` - the planets in Chaldean order from Mars in the first decan
  of Aries. This is the school of the Golden Dawn and of the tarot table.
* `ruler_triplicity` - the first decan belongs to the sign's own ruler, the
  second and third to the rulers of the next two signs of the same element.
  The rule is the Vedic drekkana's, but note: Jyotish applies it to the
  *sidereal* longitude, so on a tropical position it is the Western use of the
  rule, not the Vedic drekkana of that body.
"""

from __future__ import annotations

import math
from typing import Iterable, Literal

from eldermind_core.core.config import DEGREES_PER_SIGN, ZODIAC_SIGNS
from eldermind_core.core.decan_constants import (
    COURT_CARDS,
    COURT_RANKS,
    COURT_SPAN_DEGREES,
    COURT_SPAN_START_DEGREE,
    DECAN_COUNT,
    DECAN_DEGREES,
    DECANS,
    DECANS_PER_SIGN,
    MAJOR_ARCANA,
    MAJOR_SECOND,
    MAJOR_TITLES_BOOK_T,
    MODERN_SIGN_RULERS,
    PRINCESS_CHERUBIC_SIGN,
    SIGN_ELEMENTS,
    SUIT_BY_ELEMENT,
    TRADITIONAL_SIGN_RULERS,
)

SUIT_ELEMENT = {suit: element for element, suit in SUIT_BY_ELEMENT.items()}

RulerSet = Literal["traditional", "modern"]


def normalize_longitude(longitude: float) -> float:
    """Longitude folded into [0, 360). Rejects NaN and infinities."""
    if not math.isfinite(longitude):
        raise ValueError(f"longitude must be a finite number, got {longitude!r}")
    folded = longitude % 360.0
    # -1e-18 % 360 == 360.0 in floating point; that is 0 deg Aries.
    return 0.0 if folded >= 360.0 else folded


def decan_index(longitude: float) -> int:
    """Number of the decan, 0-35, counted from 0 deg Aries.

    Boundaries belong to the decan that starts there: 10.0 deg is the second
    decan of Aries, 9.999999 deg still the first.
    """
    return int(normalize_longitude(longitude) // DECAN_DEGREES) % DECAN_COUNT


def card_id(suit: str, number: int) -> str:
    """Key of a small card as used by the deck files, e.g. `cups_05`."""
    return f"{suit}_{number:02d}"


def triplicity_ruler(index: int, rulers: RulerSet = "traditional") -> str:
    """Ruler of decan `index` in the triplicity (drekkana-rule) school."""
    table = TRADITIONAL_SIGN_RULERS if rulers == "traditional" else MODERN_SIGN_RULERS
    sign_index = index // DECANS_PER_SIGN
    # Same element, next sign of the triangle: +4 signs per decan step.
    ruling_sign = ZODIAC_SIGNS[(sign_index + 4 * (index % DECANS_PER_SIGN)) % 12]
    return table[ruling_sign]


def decan_by_index(index: int, rulers: RulerSet = "traditional") -> dict:
    """Everything the tradition attaches to decan `index` (0-35)."""
    if not 0 <= index < DECAN_COUNT:
        raise ValueError(f"decan index must be 0-{DECAN_COUNT - 1}, got {index}")
    sign, suit, number, chaldean, title = DECANS[index]
    sign_index = index // DECANS_PER_SIGN
    start_in_sign = (index % DECANS_PER_SIGN) * DECAN_DEGREES
    return {
        "index": index,
        "sign": sign,
        "sign_index": sign_index,
        "element": SIGN_ELEMENTS[sign_index],
        "decan_in_sign": index % DECANS_PER_SIGN + 1,
        "start_degree_in_sign": start_in_sign,
        "end_degree_in_sign": start_in_sign + DECAN_DEGREES,
        "start_longitude": index * DECAN_DEGREES,
        "end_longitude": (index + 1) * DECAN_DEGREES,
        "card": {
            "id": card_id(suit, number),
            "suit": suit,
            "number": number,
            "title_book_t": title,
        },
        "ruler_chaldean": chaldean,
        "ruler_triplicity": triplicity_ruler(index, rulers),
    }


def decan_of(longitude: float, rulers: RulerSet = "traditional") -> dict:
    """Decan and card for a tropical ecliptic longitude.

    Adds the position itself to `decan_by_index`: the folded longitude, the
    degree within the sign and within the decan, and how far it is to the next
    decan (useful for "the Sun changes card in N degrees").
    """
    lon = normalize_longitude(longitude)
    index = decan_index(lon)
    entry = decan_by_index(index, rulers)
    degree_in_decan = lon - index * DECAN_DEGREES
    entry.update(
        {
            "longitude": round(lon, 6),
            "degree_in_sign": round(lon % DEGREES_PER_SIGN, 6),
            "degree_in_decan": round(degree_in_decan, 6),
            "degrees_to_next_decan": round(DECAN_DEGREES - degree_in_decan, 6),
        }
    )
    return entry


def decan_table(rulers: RulerSet = "traditional") -> list[dict]:
    """All 36 decans in zodiac order, for wheels, quizzes and card pages."""
    return [decan_by_index(i, rulers) for i in range(DECAN_COUNT)]


def _court_entry(suit: str, rank: str, start_sign: str | None, title: str) -> dict:
    number, part = COURT_RANKS[rank]
    entry = {
        "id": card_id(suit, number),
        "suit": suit,
        "number": number,
        "rank_golden_dawn": rank,
        "elemental_part": part,
        "element": SUIT_ELEMENT[suit],
        "title_book_t": title,
    }
    if start_sign is None:
        entry.update({"span": None, "cherubic_sign": PRINCESS_CHERUBIC_SIGN[suit]})
        return entry
    s = ZODIAC_SIGNS.index(start_sign)
    start = s * DEGREES_PER_SIGN + COURT_SPAN_START_DEGREE
    entry["span"] = {
        "start_longitude": start,
        "end_longitude": (start + COURT_SPAN_DEGREES) % 360.0,
        "start_sign": start_sign,
        "end_sign": ZODIAC_SIGNS[(s + 1) % 12],
        "start_degree_in_sign": COURT_SPAN_START_DEGREE,
        "end_degree_in_sign": COURT_SPAN_START_DEGREE,
    }
    return entry


def court_table() -> list[dict]:
    """The 16 court cards: 12 with a 30-degree span, 4 Princesses without one."""
    return [_court_entry(*row) for row in COURT_CARDS]


def court_of(longitude: float) -> dict:
    """The Knight, Queen or Prince whose span holds a tropical longitude.

    Spans run from 20 deg of a sign to 20 deg of the next; 20 deg itself opens
    the next span (as decan boundaries do). Princesses have no span.
    """
    lon = normalize_longitude(longitude)
    start_sign = ZODIAC_SIGNS[int(((lon - COURT_SPAN_START_DEGREE) % 360.0) // COURT_SPAN_DEGREES) % 12]
    for row in COURT_CARDS:
        if row[2] == start_sign:
            return _court_entry(*row)
    raise RuntimeError(f"no court card starts in {start_sign}")  # the table covers all 12


def _major_entry(number: int, name: str, kind: str, value: str) -> dict:
    return {
        "id": f"major_{number:02d}",
        "number": number,
        "name_book_t": name,
        "title_book_t": MAJOR_TITLES_BOOK_T[number],
        "attribution": {"kind": kind, "value": value, "second": MAJOR_SECOND.get(number)},
    }


def major_table() -> list[dict]:
    """The 22 trumps with their Book T attribution (12 signs, 7 planets, 3 elements)."""
    return [_major_entry(*row) for row in MAJOR_ARCANA]


def sign_arcanum(sign: str) -> dict:
    """The trump of a zodiac sign, e.g. Aries -> The Emperor."""
    for row in MAJOR_ARCANA:
        if row[2] == "sign" and row[3] == sign:
            return _major_entry(*row)
    raise ValueError(f"unknown sign {sign!r}")


def planet_arcanum(planet: str) -> dict | None:
    """The trump of one of the seven classical planets; None for Uranus, Neptune,
    Pluto and the angles, which have no trump in Book T or in Crowley."""
    for row in MAJOR_ARCANA:
        if row[2] == "planet" and row[3] == planet:
            return _major_entry(*row)
    return None


def decans_for_bodies(
    bodies: Iterable[dict], rulers: RulerSet = "traditional"
) -> list[dict]:
    """Decan of each body in a list shaped like `compute_all_planets` output.

    Each input needs `name` and `longitude`; the Ascendant dict from
    `compute_houses` fits too. Order is preserved.
    """
    return [
        {"name": body["name"], **decan_of(float(body["longitude"]), rulers)}
        for body in bodies
    ]


__all__ = [
    "card_id",
    "court_of",
    "court_table",
    "major_table",
    "planet_arcanum",
    "sign_arcanum",
    "decan_by_index",
    "decan_index",
    "decan_of",
    "decan_table",
    "decans_for_bodies",
    "normalize_longitude",
    "triplicity_ruler",
]
