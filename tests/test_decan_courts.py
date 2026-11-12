"""Court cards and trumps of the Golden Dawn (Book T, checked against Crowley's
Book of Thoth): values, not shapes. Invented longitudes only; no dates.
"""

import pytest

from eldermind_core.core.config import ZODIAC_SIGNS
from eldermind_core.core.decan_constants import COURT_CARDS, MAJOR_ARCANA
from eldermind_core.services.decans import (
    court_of,
    court_table,
    major_table,
    planet_arcanum,
    sign_arcanum,
)


def lon(sign: str, degree: float) -> float:
    return ZODIAC_SIGNS.index(sign) * 30 + degree


# --- court cards ---------------------------------------------------------------


@pytest.mark.parametrize(
    "sign, degree, card, rank",
    [
        # Book T and Crowley: Knight of Wands from 20 Scorpio to 20 Sagittarius.
        ("Scorpio", 20.0, "wands_12", "knight"),
        ("Sagittarius", 19.99, "wands_12", "knight"),
        ("Scorpio", 19.99, "cups_14", "prince"),  # Prince of Cups: 20 Libra - 20 Scorpio
        # Queen of Wands from 20 Pisces to 20 Aries: across 0 deg Aries.
        ("Pisces", 25.0, "wands_13", "queen"),
        ("Aries", 0.0, "wands_13", "queen"),
        ("Aries", 20.0, "pentacles_14", "prince"),  # Prince of Pentacles: 20 Aries - 20 Taurus
        ("Cancer", 25.0, "wands_14", "prince"),  # Prince of Wands: 20 Cancer - 20 Leo
        ("Leo", 25.0, "pentacles_12", "knight"),
        ("Gemini", 21.0, "cups_13", "queen"),
        ("Aquarius", 21.0, "cups_12", "knight"),
        ("Taurus", 21.0, "swords_12", "knight"),
        ("Virgo", 21.0, "swords_13", "queen"),
        ("Capricorn", 21.0, "swords_14", "prince"),
        ("Sagittarius", 21.0, "pentacles_13", "queen"),
        ("Libra", 21.0, "cups_14", "prince"),
    ],
)
def test_court_of_longitude(sign: str, degree: float, card: str, rank: str) -> None:
    entry = court_of(lon(sign, degree))
    assert (entry["id"], entry["rank_golden_dawn"]) == (card, rank)


def test_court_spans_tile_the_circle_once() -> None:
    spans = [c["span"] for c in court_table() if c["span"]]
    assert len(spans) == 12
    starts = sorted(s["start_longitude"] for s in spans)
    assert starts == [i * 30 + 20.0 for i in range(12)]
    for s in spans:
        assert (s["end_longitude"] - s["start_longitude"]) % 360 == 30.0


def test_ranks_map_to_the_deck_files() -> None:
    by_id = {c["id"]: c for c in court_table()}
    assert len(by_id) == 16
    # Golden Dawn rider = deck Knight (12), Prince in the chariot = deck King (14),
    # Princess = Page (11): Book T's own labels, owner's decision 12.11.
    assert by_id["wands_12"]["rank_golden_dawn"] == "knight"
    assert by_id["wands_14"]["rank_golden_dawn"] == "prince"
    assert by_id["wands_11"]["rank_golden_dawn"] == "princess"
    assert by_id["cups_13"]["elemental_part"] == "water"  # Queen = Water of Water


def test_princesses_have_no_degrees() -> None:
    princesses = [c for c in court_table() if c["rank_golden_dawn"] == "princess"]
    assert [c["cherubic_sign"] for c in princesses] == ["Leo", "Scorpio", "Aquarius", "Taurus"]
    assert all(c["span"] is None for c in princesses)
    for degree in range(0, 360, 5):
        assert court_of(degree)["rank_golden_dawn"] != "princess"


def test_court_rows_are_complete() -> None:
    assert {(s, r) for s, r, _, _ in COURT_CARDS} == {
        (s, r) for s in ("wands", "cups", "swords", "pentacles") for r in ("knight", "queen", "prince", "princess")
    }


# --- trumps --------------------------------------------------------------------


def test_trumps_cover_signs_planets_elements() -> None:
    table = major_table()
    assert [m["number"] for m in table] == list(range(22))
    kinds = [m["attribution"]["kind"] for m in table]
    assert (kinds.count("sign"), kinds.count("planet"), kinds.count("element")) == (12, 7, 3)
    assert {m["attribution"]["value"] for m in table if m["attribution"]["kind"] == "sign"} == set(ZODIAC_SIGNS)


@pytest.mark.parametrize(
    "sign, number",
    [("Aries", 4), ("Leo", 8), ("Libra", 11), ("Aquarius", 17), ("Pisces", 18), ("Sagittarius", 14)],
)
def test_sign_arcanum(sign: str, number: int) -> None:
    assert sign_arcanum(sign)["number"] == number


def test_planet_arcanum() -> None:
    # The Moon's trump is the High Priestess; the card called "The Moon" is Pisces.
    assert planet_arcanum("Moon")["id"] == "major_02"
    assert planet_arcanum("Sun")["id"] == "major_19"
    assert planet_arcanum("Saturn")["id"] == "major_21"
    assert planet_arcanum("Mars")["id"] == "major_16"
    for body in ("Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven"):
        assert planet_arcanum(body) is None


def test_double_attributions_in_book_t() -> None:
    table = {m["number"]: m for m in major_table()}
    assert table[20]["attribution"] == {"kind": "element", "value": "fire", "second": "Spirit"}
    assert table[21]["attribution"] == {"kind": "planet", "value": "Saturn", "second": "Earth"}
    assert len(MAJOR_ARCANA) == 22
