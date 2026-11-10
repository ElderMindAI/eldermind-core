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
    DECAN_COUNT,
    DECAN_DEGREES,
    DECANS,
    DECANS_PER_SIGN,
    MODERN_SIGN_RULERS,
    SIGN_ELEMENTS,
    TRADITIONAL_SIGN_RULERS,
)

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
    "decan_by_index",
    "decan_index",
    "decan_of",
    "decan_table",
    "decans_for_bodies",
    "normalize_longitude",
    "triplicity_ruler",
]
