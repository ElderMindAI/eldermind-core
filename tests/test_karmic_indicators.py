"""Karmic indicators (plan „Kundalini i Karma”, session SE).

The definitions were agreed with the owner on 2026-11-19; each test below pins
one of them:

* karmic debt = 13, 14, 16 or 19 at any stage of the reduction chain except
  the final value (a master number 11/22/33 stops the chain);
* Life Path twice: the engine method (all digits at once) and the classic
  method (day, month, year reduced first), labelled separately;
* birth day = the day of the month itself;
* expression / soul urge / personality from the full birth name;
* karmic lessons = digits 1-9 with no letter in the full birth name, plus the
  count of every digit;
* lunar nodes = true node, tropical and sidereal (Lahiri), read at 12:00 UT,
  flagged when the sign changes on the birth date anywhere on Earth.

Expected values are worked out by hand in the comments.
"""

from datetime import date

import pytest

from eldermind_core.services import numerology
from eldermind_core.services.ephemeris import compute_lunar_node_signs
from eldermind_core.services.karmic_indicators import compute_karmic_indicators
from eldermind_core.services.matrix_destiny import compute_karmic_points, compute_matrix_of_destiny
from eldermind_core.services.numerology import (
    compute_karmic_debts,
    compute_karmic_lessons,
    reduction_chain,
)


# --- reduction chain -------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "chain"),
    [
        (31, [31, 4]),
        (169, [169, 16, 7]),
        (199, [199, 19, 10, 1]),
        (29, [29, 11]),        # master number stops the chain
        (22, [22]),
        (7, [7]),
    ],
)
def test_reduction_chain_follows_engine_rule(raw, chain):
    assert reduction_chain(raw) == chain
    assert chain[-1] == numerology._digit_sum(raw)


# --- karmic debts: Life Path ----------------------------------------------

def test_life_path_debt_engine_method():
    # 1940-01-01: 1+9+4+0+0+1+0+1 = 16 -> 7
    debts = compute_karmic_debts(date(1940, 1, 1))
    assert debts["life_path"] == {"value": 7, "chain": [16, 7], "debts": [16]}
    assert debts["life_path"]["value"] == numerology.compute_life_path(date(1940, 1, 1))


def test_life_path_debt_at_middle_stage():
    # 1940-01-04: 1+9+4+0+0+1+0+4 = 19 -> 10 -> 1; 19 is not the last stage before 1
    debts = compute_karmic_debts(date(1940, 1, 4))
    assert debts["life_path"]["chain"] == [19, 10, 1]
    assert debts["life_path"]["debts"] == [19]


def test_life_path_methods_can_disagree():
    # 1940-01-07, engine: 1+9+4+0+0+1+0+7 = 22 (master, stop) -> no debt
    # classic: day 7, month 1, year 1+9+4+0 = 14 -> 5; 7+1+5 = 13 -> 4
    debts = compute_karmic_debts(date(1940, 1, 7))
    assert debts["life_path"] == {"value": 22, "chain": [22], "debts": []}
    classic = debts["life_path_classic"]
    assert classic["components"] == {"day": 7, "month": 1, "year": 5}
    assert classic["chain"] == [13, 4]
    assert classic["debts"] == [13]
    assert debts["all"] == [13]


def test_classic_keeps_master_components():
    # 1985-04-22: day 22 stays 22, month 4, year 1+9+8+5 = 23 -> 5; 31 -> 4
    classic = compute_karmic_debts(date(1985, 4, 22))["life_path_classic"]
    assert classic["components"] == {"day": 22, "month": 4, "year": 5}
    assert classic["chain"] == [31, 4]


# --- karmic debts: birth day ----------------------------------------------

@pytest.mark.parametrize("day", [13, 14, 16, 19])
def test_birth_day_debt(day):
    assert compute_karmic_debts(date(1990, 3, day))["birth_day"] == {"value": day, "debts": [day]}


@pytest.mark.parametrize("day", [1, 10, 12, 15, 17, 18, 22, 31])
def test_birth_day_without_debt(day):
    assert compute_karmic_debts(date(1990, 3, day))["birth_day"]["debts"] == []


# --- karmic debts: name numbers -------------------------------------------

def test_name_numbers_match_existing_functions_and_find_debt():
    # Jan Kowalski: J1 A1 N5 K2 O6 W5 A1 L3 S1 K2 I9 = 36 -> 9
    # vowels A O A I = 1+6+1+9 = 17 -> 8; consonants 36-17 = 19 -> 10 -> 1
    name = "Jan Kowalski"
    debts = compute_karmic_debts(date(1985, 4, 22), name)
    assert debts["expression"] == {"value": 9, "chain": [36, 9], "debts": []}
    assert debts["soul_urge"] == {"value": 8, "chain": [17, 8], "debts": []}
    assert debts["personality"] == {"value": 1, "chain": [19, 10, 1], "debts": [19]}
    assert debts["expression"]["value"] == numerology.compute_expression_number(name)
    assert debts["soul_urge"]["value"] == numerology.compute_soul_urge_number(name)
    assert debts["personality"]["value"] == numerology.compute_personality_number(name)
    assert debts["all"] == [19]


def test_three_digit_name_sum_debt():
    # Grzegorz Brzęczyszczykiewicz (ę -> e): 169 -> 16 -> 7
    debts = compute_karmic_debts(date(1985, 4, 22), "Grzegorz Brzęczyszczykiewicz")
    assert debts["expression"]["chain"] == [169, 16, 7]
    assert debts["expression"]["debts"] == [16]


def test_polish_letters_are_flattened():
    # Łucja Żółć -> LUCJA ZOLC: 3+3+3+1+1 + 8+6+3+3 = 31 -> 4
    debts = compute_karmic_debts(date(1985, 4, 22), "Łucja Żółć")
    assert debts["expression"]["chain"] == [31, 4]


@pytest.mark.parametrize("name", [None, "", "   "])
def test_without_name_name_numbers_are_none(name):
    debts = compute_karmic_debts(date(1985, 4, 22), name)
    assert debts["expression"] is None
    assert debts["soul_urge"] is None
    assert debts["personality"] is None


# --- karmic lessons --------------------------------------------------------

def test_karmic_lessons_jan_kowalski():
    # values 1,1,5,2,6,5,1,3,1,2,9
    lessons = compute_karmic_lessons("Jan Kowalski")
    assert lessons["missing"] == [4, 7, 8]
    assert lessons["counts"] == {"1": 4, "2": 2, "3": 1, "4": 0, "5": 2, "6": 1, "7": 0, "8": 0, "9": 1}


def test_karmic_lessons_count_every_name_and_y_as_seven():
    # adding the middle name "Ygor" (Y7 G7 O6 R9) removes lesson 7
    lessons = compute_karmic_lessons("Jan Ygor Kowalski")
    assert lessons["missing"] == [4, 8]
    assert lessons["counts"]["7"] == 2


@pytest.mark.parametrize("name", [None, "", "  ", "123 -"])
def test_karmic_lessons_without_letters(name):
    assert compute_karmic_lessons(name) is None


# --- Matrix of Destiny ----------------------------------------------------

def test_karmic_points_read_from_full_chart():
    # 1985-04-22: A=4, B=22, C=1+9+8+5=23 -> 5, D=4+22+5=31 -> 4,
    # E=4+22+5+4=35 -> 8; center-bottom 8+4 = 12; tail third 4+12 = 16
    points = compute_karmic_points(date(1985, 4, 22))
    assert [p["arcana_number"] for p in points["karmic_tail"]] == [4, 12, 16]
    assert [p["arcana_name"] for p in points["karmic_tail"]] == ["Cesarz", "Wisielec", "Wieża"]
    assert points["external_karma"] == {"vertex": "B", "arcana_number": 22, "arcana_name": "Głupiec"}
    chart = compute_matrix_of_destiny(date(1985, 4, 22))
    assert [p["arcana_number"] for p in points["karmic_tail"]] == chart["lines"]["karmic_tail"]
    assert points["external_karma"]["arcana_number"] == chart["core"]["left"]


# --- lunar nodes ----------------------------------------------------------

def test_lunar_nodes_j2000():
    # True node at 2000-01-01 12:00 UT ~124° (4° Leo); Lahiri ayanamsa ~23.85°
    nodes = compute_lunar_node_signs(date(2000, 1, 1))
    assert nodes["node"] == "true"
    assert nodes["reference_moment"] == "2000-01-01T12:00Z"
    trop = nodes["tropical"]
    assert trop["north_node"]["sign"] == "Leo"
    assert trop["south_node"]["sign"] == "Aquarius"
    assert trop["certain"] is True
    assert trop["possible_signs"] == ["Leo"]
    assert abs(trop["north_node"]["longitude"] - 123.95) < 0.05
    sid = nodes["sidereal"]
    assert sid["ayanamsa"] == "lahiri"
    assert sid["rahu"]["sign"] == "Cancer"
    assert sid["ketu"]["sign"] == "Capricorn"
    assert sid["certain"] is True


def test_lunar_nodes_south_is_opposite():
    nodes = compute_lunar_node_signs(date(1985, 4, 22))
    north = nodes["tropical"]["north_node"]["longitude"]
    south = nodes["tropical"]["south_node"]["longitude"]
    assert abs((south - north) % 360.0 - 180.0) < 1e-6


def test_lunar_nodes_sign_change_on_birth_date_is_flagged():
    # The true node entered Aries (from Taurus, moving backwards) on 17-18 July 2023
    nodes = compute_lunar_node_signs(date(2023, 7, 17))
    assert nodes["tropical"]["certain"] is False
    assert nodes["tropical"]["possible_signs"] == ["Taurus", "Aries"]
    assert nodes["sidereal"]["certain"] is True


# --- aggregate ------------------------------------------------------------

def test_aggregate_shape_with_and_without_name():
    with_name = compute_karmic_indicators(date(1985, 4, 22), "Jan Kowalski")
    assert with_name["schema_version"] == 1
    assert with_name["has_name"] is True
    assert with_name["numerology"]["karmic_debts"]["all"] == [19]
    assert with_name["numerology"]["karmic_lessons"]["missing"] == [4, 7, 8]
    assert set(with_name["matrix"]) == {"karmic_tail", "external_karma"}
    assert with_name["lunar_nodes"]["tropical"]["north_node"]["sign"] == "Taurus"

    without = compute_karmic_indicators(date(1985, 4, 22))
    assert without["has_name"] is False
    assert without["numerology"]["karmic_lessons"] is None
    assert without["numerology"]["karmic_debts"]["expression"] is None
    assert without["matrix"] == with_name["matrix"]


def test_existing_numerology_output_unchanged():
    """The new functions do not add keys to `compute_numerology`."""
    result = numerology.compute_numerology(date(1985, 4, 22), date(2026, 11, 19), "Jan Kowalski")
    assert set(result) == {
        "life_path", "personal_year", "expression_number", "soul_urge_number",
        "personality_number", "maturity_number", "day_number",
    }
