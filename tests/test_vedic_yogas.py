"""Value tests for the facts added in 1.0.4: Vedic houses, drishti, yogas,
Nakshatras of every body, the panchanga, Sade-Sati windows, Da Yun years,
split-definition bridges and transit channels.

The three charts below are the sidereal positions of three real reports the
model got wrong on 2026-11-02. They are kept as bare numbers on purpose: no
name, no birth date, nothing that identifies a person — this repository is
public. Each expectation is a condition checked by hand against that day's
review.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
import swisseph as swe

from eldermind_core.core.config import ZODIAC_SIGNS
from eldermind_core.core.hd_constants import HD_BODY_IDS, HD_GATE_SEQUENCE
from eldermind_core.services.bazi import compute_bazi
from eldermind_core.services.ephemeris import _longitude_to_nakshatra, compute_julian_day_ut
from eldermind_core.services.human_design import (
    compute_hd_mechanics,
    compute_transit_channels,
    transit_gate_window,
)
from eldermind_core.services.panchanga import compute_panchanga, tithi_from_elongation
from eldermind_core.services.sade_sati import compute_sade_sati
from eldermind_core.services.vedic_yogas import (
    attach_vedic_houses,
    compute_chara_karakas,
    compute_drishti,
    compute_yogas,
    ketu_position,
)

PLANET_ORDER = (
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "TrueNode",
)


def _chart(lagna: tuple[str, float], positions: dict[str, tuple[str, float, bool]]):
    def body(name: str, sign: str, degree: float, retro: bool = False) -> dict:
        return {
            "name": name,
            "longitude": ZODIAC_SIGNS.index(sign) * 30.0 + degree,
            "sign": sign,
            "degree_in_sign": degree,
            "is_retrograde": retro,
        }

    planets = [body(name, *positions[name]) for name in PLANET_ORDER]
    return attach_vedic_houses(planets, body("Ascendant", *lagna)), body("Ascendant", *lagna)


# Report reviewed 2026-11-02: Gaja-Kesari, Hamsa, Vipareeta and a Neecha Bhanga
# were described as present; Saturn was put in the Lagna's Nakshatra.
CHART_A = _chart(
    ("Gemini", 16.38),
    {
        "Sun": ("Sagittarius", 15.85, False), "Moon": ("Scorpio", 16.71, False),
        "Mercury": ("Capricorn", 4.15, False), "Venus": ("Libra", 29.42, False),
        "Mars": ("Libra", 25.43, False), "Jupiter": ("Cancer", 23.03, True),
        "Saturn": ("Gemini", 0.58, True), "Uranus": ("Aquarius", 2.35, False),
        "Neptune": ("Capricorn", 15.66, False), "Pluto": ("Scorpio", 24.37, False),
        "TrueNode": ("Taurus", 14.59, True),
    },
)

# Report reviewed 2026-11-02: headings for Vimala, Vasi and Subha Kartari.
CHART_B = _chart(
    ("Cancer", 8.35),
    {
        "Sun": ("Cancer", 2.53, False), "Moon": ("Sagittarius", 0.40, False),
        "Mercury": ("Cancer", 9.57, True), "Venus": ("Leo", 14.77, False),
        "Mars": ("Sagittarius", 21.46, True), "Jupiter": ("Aquarius", 29.12, True),
        "Saturn": ("Scorpio", 9.68, True), "Uranus": ("Scorpio", 25.32, True),
        "Neptune": ("Sagittarius", 10.17, True), "Pluto": ("Libra", 10.87, False),
        "TrueNode": ("Aries", 1.80, True),
    },
)

# The public sample report.
CHART_C = _chart(
    ("Libra", 1.69),
    {
        "Sun": ("Leo", 15.14, False), "Moon": ("Aquarius", 17.85, False),
        "Mercury": ("Leo", 18.02, False), "Venus": ("Cancer", 11.81, False),
        "Mars": ("Virgo", 19.20, False), "Jupiter": ("Virgo", 21.43, False),
        "Saturn": ("Aquarius", 2.26, True), "Uranus": ("Sagittarius", 24.73, True),
        "Neptune": ("Sagittarius", 24.82, True), "Pluto": ("Libra", 29.19, False),
        "TrueNode": ("Scorpio", 13.71, True),
    },
)


def _yogas(chart) -> dict[str, list[dict]]:
    planets, ascendant = chart
    found: dict[str, list[dict]] = {}
    for yoga in compute_yogas(planets, ascendant):
        found.setdefault(yoga["name"], []).append(yoga)
    return found


def _present(chart, name: str) -> bool:
    return any(y["present"] for y in _yogas(chart)[name])


def test_houses_count_whole_signs_from_lagna_and_moon() -> None:
    planets, _ = CHART_A
    jupiter = next(p for p in planets if p["name"] == "Jupiter")
    assert jupiter["house_number"] == 2
    assert jupiter["house_from_moon"] == 9
    saturn = next(p for p in planets if p["name"] == "Saturn")
    assert saturn["house_number"] == 1


def test_chart_a_yogas() -> None:
    yogas = _yogas(CHART_A)
    assert not _present(CHART_A, "Gaja-Kesari")
    assert "9th sign from the Moon" in yogas["Gaja-Kesari"][0]["reason"]
    assert not _present(CHART_A, "Hamsa")  # exalted, but in the 2nd house
    assert "2nd house" in yogas["Hamsa"][0]["reason"]
    assert yogas["Hamsa"][0]["from_moon"] is False
    for name in ("Harsha", "Sarala", "Vimala"):
        assert not _present(CHART_A, name)
    # The Moon is debilitated in Scorpio and nothing cancels it; an aspect of
    # Jupiter is not one of the conditions.
    neecha = yogas["Neecha Bhanga"]
    assert [y["planets"] for y in neecha] == [["Moon"]]
    assert neecha[0]["present"] is False
    assert [y["planets"] for y in yogas["Parivartana"] if y["present"]] == [["Mercury", "Saturn"]]
    assert [y["planets"] for y in yogas["Dhana"] if y["present"]] == [["Venus", "Mars"]]
    assert _present(CHART_A, "Vesi")
    assert not _present(CHART_A, "Vasi")
    assert not _present(CHART_A, "Dharma-Karmadhipati")


def test_chart_b_yogas() -> None:
    assert _present(CHART_B, "Harsha")  # 6th lord Jupiter in the 8th
    assert not _present(CHART_B, "Vimala")
    assert _present(CHART_B, "Budha-Aditya")
    assert _present(CHART_B, "Chandra-Mangala")
    assert not _present(CHART_B, "Vasi")
    assert not _present(CHART_B, "Subha Kartari")


def test_chart_c_yogas() -> None:
    yogas = _yogas(CHART_C)
    assert _present(CHART_C, "Amala")  # Venus in the 10th from the Lagna
    assert yogas["Amala"][0]["planets"] == ["Venus"]
    sasa = yogas["Sasa"][0]
    assert sasa["present"] is False and sasa["from_moon"] is True
    kemadruma = yogas["Kemadruma"][0]
    assert kemadruma["present"] is True and kemadruma["cancelled"] is True
    assert "Saturn" in kemadruma["reason"]


def test_every_listed_yoga_is_always_reported() -> None:
    names = set(_yogas(CHART_B))
    assert {
        "Gaja-Kesari", "Budha-Aditya", "Chandra-Mangala", "Ruchaka", "Bhadra",
        "Hamsa", "Malavya", "Sasa", "Harsha", "Sarala", "Vimala", "Neecha Bhanga",
        "Sunapha", "Anapha", "Durudhara", "Kemadruma", "Vesi", "Vasi",
        "Ubhayachari", "Subha Kartari", "Papa Kartari", "Parivartana",
        "Mangal Dosha", "Kala Sarpa", "Amala", "Dhana", "Dharma-Karmadhipati",
    } <= names


def test_neecha_bhanga_names_the_condition_that_holds() -> None:
    planets, ascendant = _chart(
        ("Cancer", 10.0),
        {
            "Sun": ("Leo", 5.0, False), "Moon": ("Taurus", 5.0, False),
            "Mercury": ("Leo", 20.0, False), "Venus": ("Virgo", 2.0, False),
            "Mars": ("Libra", 3.0, False), "Jupiter": ("Pisces", 8.0, False),
            "Saturn": ("Aries", 12.0, False), "Uranus": ("Aries", 1.0, False),
            "Neptune": ("Aries", 2.0, False), "Pluto": ("Aries", 3.0, False),
            "TrueNode": ("Gemini", 1.0, True),
        },
    )
    neecha = {y["planets"][0]: y for y in compute_yogas(planets, ascendant) if y["name"] == "Neecha Bhanga"}
    # Saturn in Aries: Mars, lord of Aries, is 4th from the Lagna.
    assert neecha["Saturn"]["present"] is True
    assert "(a) Mars" in neecha["Saturn"]["reason"]
    # Venus in Virgo: Mercury, lord of Virgo, is 2nd from the Lagna but 4th
    # from the Moon — a kendra counted from the Moon is enough.
    assert neecha["Venus"]["present"] is True


def test_kala_sarpa_and_mahapurusha() -> None:
    planets, ascendant = _chart(
        ("Sagittarius", 3.0),
        {
            "Sun": ("Aries", 5.0, False), "Moon": ("Gemini", 5.0, False),
            "Mercury": ("Aries", 20.0, False), "Venus": ("Taurus", 2.0, False),
            "Mars": ("Cancer", 3.0, False), "Jupiter": ("Leo", 8.0, False),
            "Saturn": ("Virgo", 12.0, False), "Uranus": ("Aries", 1.0, False),
            "Neptune": ("Aries", 2.0, False), "Pluto": ("Aries", 3.0, False),
            "TrueNode": ("Pisces", 20.0, True),
        },
    )
    yogas = {y["name"]: y for y in compute_yogas(planets, ascendant)}
    assert yogas["Kala Sarpa"]["present"] is True
    # Venus in its own sign Taurus is the 6th house: no Malavya.
    assert yogas["Malavya"]["present"] is False
    planets, ascendant = _chart(
        ("Sagittarius", 3.0),
        {**{n: ("Aries", 1.0, False) for n in PLANET_ORDER}, "Jupiter": ("Sagittarius", 9.0, False)},
    )
    hamsa = next(y for y in compute_yogas(planets, ascendant) if y["name"] == "Hamsa")
    assert hamsa["present"] is True


def test_dharma_karmadhipati_from_a_single_lord() -> None:
    planets, ascendant = _chart(
        ("Taurus", 3.0), {n: ("Aries", 1.0, False) for n in PLANET_ORDER}
    )
    yoga = next(y for y in compute_yogas(planets, ascendant) if y["name"] == "Dharma-Karmadhipati")
    assert yoga["present"] is True and yoga["planets"] == ["Saturn"]


def test_drishti_lists_aspected_signs_and_their_occupants() -> None:
    planets, ascendant = CHART_A
    jupiter = next(d for d in compute_drishti(planets, ascendant) if d["planet"] == "Jupiter")
    assert [(a["aspect"], a["sign"], a["house_number"]) for a in jupiter["aspects"]] == [
        (5, "Scorpio", 6), (7, "Capricorn", 8), (9, "Pisces", 10),
    ]
    assert jupiter["aspects"][0]["planets"] == ["Moon", "Ketu"]
    mars = next(d for d in compute_drishti(planets, ascendant) if d["planet"] == "Mars")
    assert [a["aspect"] for a in mars["aspects"]] == [4, 7, 8]


def test_nakshatra_of_every_body() -> None:
    planets, _ = CHART_A
    saturn = next(p for p in planets if p["name"] == "Saturn")
    assert _longitude_to_nakshatra(saturn["longitude"])["nakshatra_name"] == "Mrigashira"
    ketu = ketu_position(next(p for p in planets if p["name"] == "TrueNode"))
    assert ketu["sign"] == "Scorpio"
    assert _longitude_to_nakshatra(ketu["longitude"]) == {
        "nakshatra_number": 17, "nakshatra_name": "Anuradha", "nakshatra_lord": "Saturn", "pada": 4,
        "navamsa_sign": "Scorpio",
    }


@pytest.mark.parametrize(
    ("elongation", "number", "name", "paksha"),
    [
        (0.0, 1, "Pratipada", "Shukla"),
        (147.876, 13, "Trayodashi", "Shukla"),
        (179.9, 15, "Purnima", "Shukla"),
        (182.704, 16, "Pratipada", "Krishna"),
        (330.853, 28, "Trayodashi", "Krishna"),
        (359.9, 30, "Amavasya", "Krishna"),
    ],
)
def test_tithi(elongation: float, number: int, name: str, paksha: str) -> None:
    assert tithi_from_elongation(elongation) == {
        "tithi_number": number, "tithi_name": name, "paksha": paksha,
    }


def _jd(moment: datetime) -> float:
    return swe.julday(moment.year, moment.month, moment.day, moment.hour + moment.minute / 60.0)


def test_panchanga_measures_days_to_the_lunations() -> None:
    # New moon 2024-01-11 11:57 UTC, full moon 2024-01-25 17:54 UTC.
    two_days_after = compute_panchanga(_jd(datetime(2024, 1, 13, 11, 57, tzinfo=timezone.utc)))
    assert two_days_after["paksha"] == "Shukla"
    assert two_days_after["days_since_new_moon"] == pytest.approx(2.0, abs=0.01)
    assert two_days_after["days_to_full_moon"] == pytest.approx(12.25, abs=0.01)


def test_sade_sati_lists_every_window_of_the_life() -> None:
    result = compute_sade_sati("Scorpio", date(2026, 11, 2), birth_date=date(2000, 1, 1))
    cycles = [(c["relation"], c["start_date"], c["end_date"]) for c in result["cycles"]]
    assert cycles == [
        ("previous", "2011-11-15", "2020-01-24"),
        ("next", "2041-01-27", "2049-03-06"),
        ("future", "2070-11-04", "2079-01-14"),
    ]
    # The window the top-level fields describe is the one marked "next".
    assert (result["start_date"], result["end_date"]) == ("2041-01-27", "2049-03-06")


def test_sade_sati_window_under_way_at_birth() -> None:
    result = compute_sade_sati("Aquarius", date(2026, 7, 28), birth_date=date(1995, 1, 1))
    first = result["cycles"][0]
    assert first["relation"] == "previous"
    assert first["start_date"] < "1995-01-01" < first["end_date"]
    assert first["age_at_start"] == 0.0
    assert result["cycles"][1]["relation"] == "current"


def test_sade_sati_phases_follow_the_first_entry_and_keep_retrograde_returns() -> None:
    # Saturn (sidereal) entered Aquarius on 2022-04-29, went back to Capricorn
    # on 2022-07-12 and returned on 2023-01-17; it leaves Pisces on 2027-06-02,
    # is back from 2027-10-20 and leaves for good on 2028-02-23. Until 1.0.6 the
    # top-level peak began on 2023-01-17 while `cycles` began it on 2022-04-29,
    # and nothing showed the return to Pisces — a report called 2027-06-02 the
    # definitive end.
    result = compute_sade_sati("Aquarius", date(2026, 11, 2), birth_date=date(1995, 1, 1))
    current = next(c for c in result["cycles"] if c["relation"] == "current")
    assert result["phases"] == current["phases"]
    segments = {p["phase"]: [(s["start"], s["end"]) for s in p["segments"]] for p in result["phases"]}
    assert segments == {
        "rising": [("2020-01-24", "2022-04-29"), ("2022-07-12", "2023-01-17")],
        "peak": [("2022-04-29", "2022-07-12"), ("2023-01-17", "2025-03-29")],
        "setting": [("2025-03-29", "2027-06-02"), ("2027-10-20", "2028-02-23")],
    }
    assert (result["end_date"], result["final_end_date"]) == ("2027-06-02", "2028-02-23")
    assert current["final_end_date"] == "2028-02-23"
    back_in_pisces = compute_sade_sati("Aquarius", date(2027, 11, 1))
    assert (back_in_pisces["status"], back_in_pisces["phase"]) == ("active", "setting")
    assert back_in_pisces["final_end_date"] == "2028-02-23"


def test_chara_karakas_rank_the_classical_seven_by_degree() -> None:
    # Pluto at 29° Libra stands highest in its sign and is no karaka: on
    # 2026-11-02 a report made it the Atmakaraka of this chart.
    planets, _ = CHART_C
    ranked = [(k["karaka"], k["planet"]) for k in compute_chara_karakas(planets)]
    assert ranked == [
        ("Atmakaraka", "Jupiter"), ("Amatyakaraka", "Mars"), ("Bhratrikaraka", "Mercury"),
        ("Matrikaraka", "Moon"), ("Putrakaraka", "Sun"), ("Gnatikaraka", "Venus"),
        ("Darakaraka", "Saturn"),
    ]


def test_nakshatra_parivartana() -> None:
    # Moon in Shatabhisha (Rahu), Rahu in Anuradha (Saturn), Saturn in
    # Dhanishta (Mars): a chain, not an exchange — three reports called it one.
    absent = _yogas(CHART_C)["Nakshatra Parivartana"]
    assert [y["present"] for y in absent] == [False]
    assert "Saturn Mars" in absent[0]["reason"] and "Rahu Saturn" in absent[0]["reason"]
    planets, ascendant = CHART_C
    # Saturn moved to Bharani (Venus) while Venus stays in Pushya (Saturn).
    moved = [
        dict(p, longitude=20.0, sign="Aries", degree_in_sign=20.0) if p["name"] == "Saturn" else p
        for p in planets
    ]
    present = [y for y in compute_yogas(moved, ascendant) if y["name"] == "Nakshatra Parivartana"]
    assert [(y["present"], y["planets"]) for y in present] == [(True, ["Venus", "Saturn"])]


def test_da_yun_calendar_years_and_current_pillar() -> None:
    jd_ut, _ = compute_julian_day_ut(date(2000, 6, 15), time(12, 0), "UTC")
    bazi = compute_bazi(
        date(2000, 6, 15), time(12, 0), gender="male", julian_day_ut=jd_ut,
        reference_date=date(2026, 11, 2),
    )
    pillars = bazi["da_yun"]
    first_start = date(2000, 6, 15) + timedelta(days=bazi["da_yun_start_age_precise"] * 365.2425)
    assert pillars[0]["start_year"] == first_start.year
    for earlier, later in zip(pillars, pillars[1:]):
        assert later["start_year"] == earlier["end_year"]
        assert later["start_year"] - earlier["start_year"] == 10
    current = [p for p in pillars if p["is_current"]]
    assert len(current) == 1
    assert current[0]["start_year"] <= 2026 <= current[0]["end_year"]


def _activations(gates: list[tuple[int, int]]) -> list[dict]:
    return [
        {"name": name, "gate": gate, "line": line, "longitude": 0.0}
        for name, (gate, line) in zip(HD_BODY_IDS, gates)
    ]


# Chart A's bodygraph, gate.line per body in HD_BODY_IDS order.
PERSONALITY_A = _activations([(38, 1), (39, 1), (9, 6), (16, 3), (9, 3), (60, 2), (43, 5),
                              (43, 1), (7, 4), (12, 2), (30, 2), (19, 3), (26, 2)])
DESIGN_A = _activations([(48, 3), (21, 3), (6, 1), (16, 6), (9, 6), (46, 1), (1, 2),
                         (6, 1), (33, 6), (15, 1), (30, 1), (19, 1), (5, 5)])


def test_split_bridges() -> None:
    mechanics = compute_hd_mechanics(PERSONALITY_A, DESIGN_A)
    assert mechanics["definition"] == "Split Definition"
    bridges = mechanics["split_bridges"]
    assert bridges["components"] == [["Throat", "Spleen"], ["G", "Sacral"]]
    assert [(b["gate"], b["with_natal_gate"]) for b in bridges["single_gate"]] == [(8, 1), (13, 33), (31, 7)]
    assert {b["channel"] for b in bridges["channel_pairs"]} == {"10-20", "10-57", "20-34", "27-50", "34-57"}


def test_single_definition_has_no_bridges() -> None:
    single = _activations([(34, 1), (20, 1)] + [(34, 1)] * 11)
    assert compute_hd_mechanics(single, single)["split_bridges"] is None


def _longitude_in_gate(gate: int) -> float:
    return (302.0 + HD_GATE_SEQUENCE.index(gate) * 5.625 + 2.0) % 360.0


def test_transit_channels_with_natal_gates() -> None:
    transit = [
        {"name": "Sun", "longitude": _longitude_in_gate(44)},
        {"name": "Pluto", "longitude": _longitude_in_gate(41)},
        {"name": "Mars", "longitude": _longitude_in_gate(15)},  # 5-15 is already natal
    ]
    channels = compute_transit_channels(PERSONALITY_A, DESIGN_A, transit)
    found = {(c["transit_body"], c["channel"]) for c in channels}
    assert ("Sun", "26-44") in found
    assert ("Pluto", "30-41") in found
    assert not any(c["channel"] == "5-15" for c in channels)
    sun = next(c for c in channels if c["channel"] == "26-44")
    assert sun["natal_gate"] == 26 and sun["natal_bodies"] == ["Pluto (Personality)"]
    assert sun["newly_defined_centers"] == ["Heart"]


def test_transit_earth_is_read_opposite_the_sun() -> None:
    # Gates 24 and 44 face each other: the Sun in 24 puts the Earth in 44.
    channels = compute_transit_channels(
        PERSONALITY_A, DESIGN_A, [{"name": "Sun", "longitude": _longitude_in_gate(24)}]
    )
    assert [(c["transit_body"], c["channel"]) for c in channels] == [("Earth", "26-44")]


def test_transit_gate_window_of_the_sun() -> None:
    jd = _jd(datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc))
    window = transit_gate_window("Sun", jd)
    assert window["active_from"] <= "2026-11-02" <= window["active_until"]
    assert 5.0 < window["duration_days"] < 6.5
