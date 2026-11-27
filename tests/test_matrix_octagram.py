"""Full Matrix of Destiny: octagram, inner points and the 0-80 age ring.

Control values were read off two independent reference charts and checked
point by point (56/56 for the first date). The dates are used bare — no
names belong in this public repository.
"""

from datetime import date

import pytest

from eldermind_core.services.matrix_destiny import (
    TAROT_ARCANA,
    compute_matrix_of_destiny,
)

DATE_A = date(1993, 9, 1)
DATE_B = date(1993, 10, 13)
REFERENCE = date(2026, 11, 27)

VERTICES = (
    "left", "top_left", "top", "top_right",
    "right", "bottom_right", "bottom", "bottom_left",
)


@pytest.fixture(scope="module")
def chart_a() -> dict:
    return compute_matrix_of_destiny(DATE_A, REFERENCE)


@pytest.fixture(scope="module")
def chart_b() -> dict:
    return compute_matrix_of_destiny(DATE_B, REFERENCE)


# --- octagram -------------------------------------------------------------

def test_octagram_vertices_date_a(chart_a: dict) -> None:
    octagram = chart_a["octagram"]
    values = {key: octagram[key]["value"] for key in VERTICES}
    assert values == {
        "left": 1, "top_left": 10, "top": 9, "top_right": 4,
        "right": 22, "bottom_right": 9, "bottom": 5, "bottom_left": 6,
    }
    assert octagram["center"]["value"] == 10


def test_octagram_inner_points_date_a(chart_a: dict) -> None:
    octagram = chart_a["octagram"]
    inner = {key: (octagram[key]["in1"], octagram[key]["in2"]) for key in VERTICES}
    assert inner == {
        "left": (12, 11), "top": (10, 19), "right": (9, 5), "bottom": (20, 15),
        "top_left": (3, 20), "top_right": (18, 14),
        "bottom_right": (10, 19), "bottom_left": (22, 16),
    }


def test_octagram_vertices_date_b(chart_b: dict) -> None:
    octagram = chart_b["octagram"]
    values = {key: octagram[key]["value"] for key in VERTICES}
    assert values == {
        "left": 13, "top_left": 5, "top": 10, "top_right": 5,
        "right": 22, "bottom_right": 4, "bottom": 9, "bottom_left": 22,
    }
    assert octagram["center"]["value"] == 9


def test_octagram_names_match_arcana(chart_a: dict) -> None:
    octagram = chart_a["octagram"]
    for key in (*VERTICES, "center"):
        assert octagram[key]["name"] == TAROT_ARCANA[octagram[key]["value"]]


def test_octagram_agrees_with_core(chart_a: dict) -> None:
    """The four straight vertices are the old `core` — one source of truth."""
    for key in ("left", "top", "right", "bottom", "center"):
        assert chart_a["octagram"][key]["value"] == chart_a["core"][key]


def test_heart_points_date_a(chart_a: dict) -> None:
    assert chart_a["heart_points"] == {"left": 21, "top": 11}


def test_love_money_date_a(chart_a: dict) -> None:
    assert chart_a["love_money"] == {"love": 8, "mid": 20, "money": 7}


# --- age ring -------------------------------------------------------------

RING_A = {
    0: [13, 12, 5, 11, 5, 21, 4],
    10: [21, 11, 3, 19, 11, 10, 19],
    20: [4, 22, 8, 13, 3, 17, 21],
    30: [16, 12, 20, 8, 11, 3, 7],
    40: [3, 8, 12, 4, 17, 13, 22],
    50: [14, 5, 19, 14, 6, 19, 6],
    60: [21, 16, 9, 11, 10, 17, 5],
    70: [19, 13, 20, 7, 15, 8, 9],
}


def _decade(ring: list[dict], start: int) -> list[int]:
    """The 7 points strictly between the vertex at `start` and the next one."""
    return [p["arcana"] for p in ring if start < p["age"] < start + 10]


def test_timeline_decades_follow_the_ring(chart_a: dict) -> None:
    """1.1.0: each decade is the vertex the ring reaches at that age."""
    decades = chart_a["timeline"]["decades"]
    assert {d: (e["vertex"], e["arcana_number"]) for d, e in decades.items()} == {
        "20": ("top", 9),
        "30": ("top_right", 4),
        "40": ("right", 22),
        "50": ("bottom_right", 9),
        "60": ("bottom", 5),
    }
    assert chart_a["timeline"]["highlighted_decade"] == "30"
    assert chart_a["timeline"]["current_age"] == 33


def test_relationship_line_is_deprecated_but_kept(chart_a: dict) -> None:
    assert chart_a["lines"]["relationship"] == [9, 20, 20]
    assert "lines.relationship" in chart_a["deprecated"]


def test_age_ring_has_64_points(chart_a: dict) -> None:
    ring = chart_a["age_ring"]
    assert len(ring) == 64
    assert [p["age"] for p in ring] == [i * 1.25 for i in range(64)]


@pytest.mark.parametrize("start", sorted(RING_A))
def test_age_ring_date_a(chart_a: dict, start: int) -> None:
    assert _decade(chart_a["age_ring"], start) == RING_A[start]


def test_age_ring_first_decade_date_b(chart_b: dict) -> None:
    assert _decade(chart_b["age_ring"], 0) == [17, 4, 22, 18, 5, 5, 10]


def test_age_ring_vertices_follow_octagram(chart_a: dict) -> None:
    """0 = left, 10 = top-left, 20 = top ... 70 = bottom-left."""
    by_age = {p["age"]: p for p in chart_a["age_ring"]}
    for index, key in enumerate(VERTICES):
        point = by_age[index * 10.0]
        assert point["level"] == 0
        assert point["arcana"] == chart_a["octagram"][key]["value"]
        assert point["label"] == str(index * 10)


def test_age_ring_levels_and_labels(chart_a: dict) -> None:
    decade = [p for p in chart_a["age_ring"] if 10 <= p["age"] < 20]
    assert [p["level"] for p in decade] == [0, 3, 2, 3, 1, 3, 2, 3]
    assert [p["label"] for p in decade] == [
        "10", "11–12", "12–13", "13–14", "15", "16–17", "17–18", "18–19",
    ]


def test_age_ring_point_fields(chart_a: dict) -> None:
    for point in chart_a["age_ring"]:
        assert 1 <= point["arcana"] <= 22
        assert point["name"] == TAROT_ARCANA[point["arcana"]]


def test_age_ring_calendar_years(chart_a: dict) -> None:
    by_age = {p["age"]: p for p in chart_a["age_ring"]}
    # Every point sits on a whole month: 1.25 years = 15 months.
    assert by_age[0.0]["start_date"] == "1993-09-01"
    assert by_age[1.25]["start_date"] == "1994-12-01"
    assert by_age[1.25]["calendar_year"] == 1994
    assert by_age[3.75]["calendar_year"] == 1997
    assert by_age[40.0]["calendar_year"] == 2033


def test_age_ring_leap_day_birth_does_not_crash() -> None:
    ring = compute_matrix_of_destiny(date(2000, 2, 29), REFERENCE)["age_ring"]
    by_age = {p["age"]: p for p in ring}
    assert by_age[5.0]["start_date"] == "2005-02-28"
    assert by_age[2.5]["start_date"] == "2002-08-29"


# --- current point --------------------------------------------------------

def test_current_and_next_point(chart_a: dict) -> None:
    # 2026-11-27 is 33 years and ~3 months after 1993-09-01: the segment that
    # opened at 32.5 (2026-03-01) and closes at 33.75 (2027-06-01).
    current, following = chart_a["current_point"], chart_a["next_point"]
    assert current["age"] == 32.5
    assert current["arcana"] == 12
    assert following["age"] == 33.75
    assert following["arcana"] == 20
    assert chart_a["age_exact"] == pytest.approx(33.24, abs=0.01)


def test_current_point_switches_on_start_date() -> None:
    on_day = compute_matrix_of_destiny(DATE_A, date(2026, 3, 1))
    day_before = compute_matrix_of_destiny(DATE_A, date(2026, 2, 28))
    assert on_day["current_point"]["age"] == 32.5
    assert day_before["current_point"]["age"] == 31.25


def test_current_point_at_birth() -> None:
    chart = compute_matrix_of_destiny(DATE_A, DATE_A)
    assert chart["current_point"]["age"] == 0.0
    assert chart["next_point"]["age"] == 1.25


def test_last_segment_has_no_next_point() -> None:
    chart = compute_matrix_of_destiny(DATE_A, date(2073, 1, 1))  # ~79.3
    assert chart["current_point"]["age"] == 78.75
    assert chart["next_point"] is None


def test_outside_ring_has_no_current_point() -> None:
    after = compute_matrix_of_destiny(DATE_A, date(2073, 9, 1))  # exactly 80
    assert after["current_point"] is None
    assert after["next_point"] is None
    before = compute_matrix_of_destiny(DATE_A, date(1993, 8, 31))
    assert before["current_point"] is None
    assert before["next_point"]["age"] == 0.0


# --- synthetic dates ------------------------------------------------------

@pytest.mark.parametrize(
    "birth",
    [date(1900, 1, 1), date(1949, 12, 31), date(1999, 9, 29), date(2024, 7, 22)],
)
def test_all_values_in_range(birth: date) -> None:
    chart = compute_matrix_of_destiny(birth, REFERENCE)
    numbers = [chart["octagram"][k][f] for k in VERTICES for f in ("value", "in1", "in2")]
    numbers += list(chart["heart_points"].values()) + list(chart["love_money"].values())
    numbers += [p["arcana"] for p in chart["age_ring"]]
    assert all(1 <= n <= 22 for n in numbers)
