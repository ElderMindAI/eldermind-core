"""Decans and Golden Dawn small cards: values, not shapes.

Only invented positions and one invented date; eldermind-core is public.
"""

from datetime import date, time

import pytest

from eldermind_core.core.config import ZODIAC_SIGNS
from eldermind_core.core.decan_constants import (
    CHALDEAN_DECAN_ORDER,
    DECANS,
    FIRST_NUMBER_BY_MODALITY,
    SIGN_ELEMENTS,
    SIGN_MODALITIES,
    SUIT_BY_ELEMENT,
)
from eldermind_core.services.decans import (
    card_id,
    decan_by_index,
    decan_index,
    decan_of,
    decan_table,
    decans_for_bodies,
    triplicity_ruler,
)
from eldermind_core.services.ephemeris import compute_all_planets, compute_julian_day_ut


# --- the table itself ------------------------------------------------------


def test_table_has_36_distinct_cards() -> None:
    assert len(DECANS) == 36
    assert len({(suit, number) for _, suit, number, _, _ in DECANS}) == 36


@pytest.mark.parametrize("index", range(36))
def test_every_row_follows_the_golden_dawn_rules(index: int) -> None:
    """Re-derive each row: element -> suit, modality -> number, Chaldean ruler."""
    sign, suit, number, ruler, _ = DECANS[index]
    sign_index = index // 3
    assert sign == ZODIAC_SIGNS[sign_index]
    assert suit == SUIT_BY_ELEMENT[SIGN_ELEMENTS[sign_index]]
    assert number == FIRST_NUMBER_BY_MODALITY[SIGN_MODALITIES[sign_index]] + index % 3
    assert ruler == CHALDEAN_DECAN_ORDER[index % 7]


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        # Rows copied from the Book T table "Lord of / Decan / In".
        (0, ("Aries", "wands", 2, "Mars", "Dominion")),
        (12, ("Leo", "wands", 5, "Saturn", "Strife")),
        (21, ("Scorpio", "cups", 5, "Mars", "Loss in Pleasure")),
        (26, ("Sagittarius", "wands", 10, "Saturn", "Oppression")),
        (33, ("Pisces", "cups", 8, "Saturn", "Abandoned Success")),
        (35, ("Pisces", "cups", 10, "Mars", "Perfected Success")),
    ],
)
def test_rows_match_book_t(index: int, expected: tuple) -> None:
    assert DECANS[index] == expected


def test_mars_rules_one_decan_more_than_the_others() -> None:
    """Book T: 36 decans over 7 planets, Mars gets the extra one (Pisces III + Aries I)."""
    counts = {planet: 0 for planet in CHALDEAN_DECAN_ORDER}
    for _, _, _, ruler, _ in DECANS:
        counts[ruler] += 1
    assert counts.pop("Mars") == 6
    assert set(counts.values()) == {5}


# --- longitude -> decan ----------------------------------------------------


@pytest.mark.parametrize(
    ("longitude", "index"),
    [
        (0.0, 0),
        (9.999999, 0),
        (10.0, 1),
        (19.999999, 1),
        (20.0, 2),
        (29.999999, 2),
        (30.0, 3),
        (215.0, 21),  # 5 deg Scorpio
        (349.999999, 34),
        (350.0, 35),
        (359.999999, 35),
        (360.0, 0),
        (370.0, 1),
        (-0.000001, 35),
        (-10.0, 35),
        (-10.000001, 34),
        (720.0, 0),
    ],
)
def test_decan_index_at_boundaries(longitude: float, index: int) -> None:
    assert decan_index(longitude) == index


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_longitude_is_rejected(bad: float) -> None:
    with pytest.raises(ValueError):
        decan_index(bad)


def test_decan_of_five_scorpio() -> None:
    entry = decan_of(215.0)
    assert entry["sign"] == "Scorpio"
    assert entry["decan_in_sign"] == 1
    assert entry["start_degree_in_sign"] == 0.0
    assert entry["end_degree_in_sign"] == 10.0
    assert entry["card"] == {
        "id": "cups_05",
        "suit": "cups",
        "number": 5,
        "title_book_t": "Loss in Pleasure",
    }
    assert entry["ruler_chaldean"] == "Mars"
    assert entry["ruler_triplicity"] == "Mars"
    assert entry["degree_in_sign"] == 5.0
    assert entry["degree_in_decan"] == 5.0
    assert entry["degrees_to_next_decan"] == 5.0


def test_decan_of_last_degree_of_pisces() -> None:
    entry = decan_of(359.5)
    assert entry["index"] == 35
    assert entry["card"]["id"] == "cups_10"
    assert entry["start_longitude"] == 350.0
    assert entry["end_longitude"] == 360.0
    assert entry["degrees_to_next_decan"] == 0.5


def test_decan_of_wraps_negative_longitude() -> None:
    assert decan_of(-355.0)["card"]["id"] == "wands_02"  # 5 deg Aries


def test_decan_by_index_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        decan_by_index(36)
    with pytest.raises(ValueError):
        decan_by_index(-1)


def test_card_id_matches_deck_file_names() -> None:
    assert card_id("cups", 5) == "cups_05"
    assert card_id("wands", 10) == "wands_10"


def test_decan_table_is_in_zodiac_order() -> None:
    table = decan_table()
    assert [row["index"] for row in table] == list(range(36))
    assert table[0]["card"]["id"] == "wands_02"
    assert table[21]["card"]["id"] == "cups_05"
    assert table[35]["card"]["id"] == "cups_10"


# --- triplicity school -----------------------------------------------------


@pytest.mark.parametrize(
    ("sign_index", "traditional", "modern"),
    [
        (0, ("Mars", "Sun", "Jupiter"), ("Mars", "Sun", "Jupiter")),  # Aries
        (1, ("Venus", "Mercury", "Saturn"), ("Venus", "Mercury", "Saturn")),  # Taurus
        (4, ("Sun", "Jupiter", "Mars"), ("Sun", "Jupiter", "Mars")),  # Leo
        (6, ("Venus", "Saturn", "Mercury"), ("Venus", "Uranus", "Mercury")),  # Libra
        (7, ("Mars", "Jupiter", "Moon"), ("Pluto", "Neptune", "Moon")),  # Scorpio
        (10, ("Saturn", "Mercury", "Venus"), ("Uranus", "Mercury", "Venus")),  # Aquarius
        (11, ("Jupiter", "Moon", "Mars"), ("Neptune", "Moon", "Pluto")),  # Pisces
    ],
)
def test_triplicity_rulers(sign_index: int, traditional: tuple, modern: tuple) -> None:
    first = sign_index * 3
    assert tuple(triplicity_ruler(first + k) for k in range(3)) == traditional
    assert tuple(triplicity_ruler(first + k, "modern") for k in range(3)) == modern


def test_schools_differ_where_they_should() -> None:
    """Five Scorpio: both schools say Mars. Fifteen Scorpio: Sun against Jupiter."""
    assert decan_of(215.0)["ruler_chaldean"] == decan_of(215.0)["ruler_triplicity"] == "Mars"
    assert decan_of(225.0)["ruler_chaldean"] == "Sun"
    assert decan_of(225.0)["ruler_triplicity"] == "Jupiter"


# --- with the ephemeris ----------------------------------------------------


def test_sun_card_on_an_invented_date() -> None:
    """3 Feb 2001, 12:00 UTC: the Sun near 14 deg Aquarius, the 6 of Swords."""
    jd_ut, _ = compute_julian_day_ut(date(2001, 2, 3), time(12, 0), "UTC")
    bodies = decans_for_bodies(compute_all_planets(jd_ut=jd_ut))
    sun = next(body for body in bodies if body["name"] == "Sun")
    assert sun["sign"] == "Aquarius"
    assert 13.0 < sun["degree_in_sign"] < 16.0
    assert sun["card"]["id"] == "swords_06"
    assert sun["card"]["title_book_t"] == "Earned Success"
    assert sun["ruler_chaldean"] == "Mercury"
    assert sun["ruler_triplicity"] == "Mercury"  # Gemini, the next air sign
