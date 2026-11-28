"""Knowledge file of the 192 incarnation cross names (S8b) and its lookup.

The file holds names only; these tests pin its structure and prove that for every cross the
engine can produce, the four gates in the table are exactly the engine's four gates.
"""

from __future__ import annotations

import collections
import re

import pytest

from eldermind_core.core.hd_constants import HD_CROSS_ANGLE_BY_PROFILE, HD_GATE_SEQUENCE
from eldermind_core.knowledge import AVAILABLE, INCARNATION_CROSSES_FILE, incarnation_cross, load
from eldermind_core.services.human_design import compute_human_design, longitude_to_gate_line

ANGLES = ("Right Angle", "Left Angle", "Juxtaposition")
VARIANTS = {"Right Angle": 4, "Left Angle": 2, "Juxtaposition": 1}
PL_PREFIX = {"Right Angle": "Prawy Krzyż ", "Left Angle": "Lewy Krzyż ", "Juxtaposition": "Naprzeciwległy Krzyż "}
EN_PREFIX = {"Right Angle": "Right Angle Cross of ", "Left Angle": "Left Angle Cross of ",
             "Juxtaposition": "Juxtaposition Cross of "}
GATE = 360.0 / 64
LINE = GATE / 6
START = 302.0


@pytest.fixture(scope="module")
def crosses() -> list[dict]:
    return load(INCARNATION_CROSSES_FILE)["crosses"]


def test_192_entries_with_all_fields(crosses):
    assert len(crosses) == 192
    for c in crosses:
        assert set(c) == {"angle", "gates", "variant", "name_pl", "name_en", "source_url"}
        assert c["angle"] in ANGLES
        assert len(c["gates"]) == 4 and all(1 <= g <= 64 for g in c["gates"])
        assert c["source_url"].startswith("https://www.humandesignpopolsku.pl/incarnation-crosses-")
        assert c["name_pl"].startswith(PL_PREFIX[c["angle"]]), c
        assert c["name_en"].startswith(EN_PREFIX[c["angle"]]), c
        assert c["name_pl"] == c["name_pl"].strip() and "  " not in c["name_pl"]
        assert c["name_en"] == c["name_en"].strip() and "  " not in c["name_en"]


@pytest.mark.parametrize("angle", ANGLES)
def test_each_personality_sun_gate_exactly_once_per_angle(crosses, angle):
    suns = collections.Counter(c["gates"][0] for c in crosses if c["angle"] == angle)
    assert sorted(suns) == list(range(1, 65))
    assert set(suns.values()) == {1}


def test_gates_follow_the_mandala(crosses):
    idx = {g: i for i, g in enumerate(HD_GATE_SEQUENCE)}
    for c in crosses:
        ps, pe, ds, de = (idx[g] for g in c["gates"])
        assert (pe - ps) % 64 == 32 and (de - ds) % 64 == 32, c  # Earth opposite Sun
        # 88° of solar arc back: 16 gates for lines 1–4 Right Angle, 15 for Left Angle and Juxtaposition
        assert (ds - ps) % 64 == (48 if c["angle"] == "Right Angle" else 49), c


def _stem(name: str) -> str:
    return re.sub(r" \d$", "", name)


@pytest.mark.parametrize("angle", ANGLES)
def test_variants_share_one_name(crosses, angle):
    families_pl = collections.defaultdict(list)
    families_en = collections.defaultdict(list)
    for c in (c for c in crosses if c["angle"] == angle):
        families_pl[_stem(c["name_pl"])].append(c)
        families_en[_stem(c["name_en"])].append(c)
    n = VARIANTS[angle]
    assert len(families_pl) == len(families_en) == 64 // n
    for fam in list(families_pl.values()) + list(families_en.values()):
        assert sorted(c["variant"] for c in fam) == list(range(1, n + 1))
        assert len({frozenset(c["gates"]) for c in fam}) == 1  # one cross = one set of four gates
        for c in fam:
            if n > 1:  # the variant number is part of the name (the Polish source numbers them)
                assert c["name_pl"].endswith(f" {c['variant']}") and c["name_en"].endswith(f" {c['variant']}")
            else:
                assert not re.search(r" \d$", c["name_pl"]) and not re.search(r" \d$", c["name_en"])


def test_right_angle_sphinx_four_variants(crosses):
    sphinx = sorted((c for c in crosses if "Sphinx" in c["name_en"]), key=lambda c: c["variant"])
    assert [c["gates"] for c in sphinx] == [[13, 7, 1, 2], [2, 1, 13, 7], [7, 13, 2, 1], [1, 2, 7, 13]]
    assert [c["name_pl"] for c in sphinx] == [f"Prawy Krzyż Sfinksa {i}" for i in range(1, 5)]


def test_left_and_juxtaposition_share_gates_but_not_names(crosses):
    by = {(c["angle"], c["gates"][0]): c for c in crosses}
    for g in range(1, 65):
        left, jux = by[("Left Angle", g)], by[("Juxtaposition", g)]
        assert left["gates"] == jux["gates"]
        assert left["name_en"] != jux["name_en"]


def _engine_cross(p_sun_lon: float) -> tuple[str, list[int]]:
    """Cross the engine assigns for a Personality Sun at this longitude (88° solar arc)."""
    p, d = longitude_to_gate_line(p_sun_lon), longitude_to_gate_line(p_sun_lon - 88.0)
    gates = [p["gate"], longitude_to_gate_line(p_sun_lon + 180)["gate"],
             d["gate"], longitude_to_gate_line(p_sun_lon - 88.0 + 180)["gate"]]
    return HD_CROSS_ANGLE_BY_PROFILE[f"{p['line']}/{d['line']}"], gates


def test_table_matches_engine_for_every_cross():
    """Every gate × line of the Personality Sun (and the narrow 4/1 band) hits a table entry with the
    engine's own four gates — all 192 entries are reached."""
    hit = set()
    for i in range(64):
        for k in range(48):  # 8 samples per line, both edges avoided
            lon = START + i * GATE + (k + 0.5) * GATE / 48
            angle, gates = _engine_cross(lon)
            entry = incarnation_cross(angle, gates)
            assert entry is not None, (lon, angle, gates)
            hit.add((angle, gates[0]))
        # Juxtaposition (4/1) lives in a 0.125° band: Design Sun in the first 13 % of line 1 of gate i
        # puts the Personality Sun (88° on) at the end of line 4 of its gate.
        for frac in (0.02, 0.06, 0.10):
            angle, gates = _engine_cross(START + i * GATE + frac * LINE + 88.0)
            assert angle == "Juxtaposition", (i, frac, angle)
            assert incarnation_cross(angle, gates) is not None, (i, gates)
            hit.add((angle, gates[0]))
    assert len(hit) == 192


def test_engine_charts_resolve_to_names():
    """Real ephemeris: a year of birth moments every ~7 h — every cross the engine reports has a name."""
    jd0 = 2448257.5  # 1991-01-01 00:00 UT
    seen = set()
    for n in range(1260):
        m = compute_human_design(jd0 + n * 0.29)["mechanics"]
        entry = incarnation_cross(m["incarnation_cross_angle"], m["incarnation_cross_gates"])
        assert entry is not None, m
        assert entry["gates"] == m["incarnation_cross_gates"]
        seen.add((entry["angle"], entry["gates"][0]))
    assert len({g for a, g in seen if a == "Right Angle"}) == 64


def test_lookup_refuses_wrong_gates():
    assert incarnation_cross("Right Angle", [13, 7, 1, 2])["name_en"] == "Right Angle Cross of the Sphinx 1"
    assert incarnation_cross("Right Angle", [13, 7, 2, 1]) is None  # design pair swapped
    assert incarnation_cross("Left Angle", [13, 7, 1, 2]) is None  # Left Angle of 13 has other design gates
    assert incarnation_cross("Right Angle", [13, 7, 1]) is None
    assert incarnation_cross("Up Angle", [13, 7, 1, 2]) is None


def test_lookup_returns_a_copy():
    e = incarnation_cross("Juxtaposition", [1, 2, 4, 49])
    e["name_pl"] = "x"
    assert incarnation_cross("Juxtaposition", [1, 2, 4, 49])["name_pl"] == "Naprzeciwległy Krzyż Autoekspresji"


def test_not_exposed_as_api_knowledge_set():
    # /v1/knowledge/{system} serves AVAILABLE; the cross names are for the report first.
    assert INCARNATION_CROSSES_FILE not in AVAILABLE.values()
