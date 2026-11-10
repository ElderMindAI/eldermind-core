"""Year windows (the "Okna" calendar): spans, house stays, retrogrades,
eclipses, personal months, BaZi months.

No people and no real birth data: natal points are placed where a transiting
planet stands at a chosen moment, so the right answer follows from the
ephemeris itself. Eclipse and station dates are checked against the
published 2027 almanac (NASA eclipse catalogue).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import cnlunar
import pytest

from eldermind_core.services import year_windows as yw
from eldermind_core.services.ephemeris import compute_transit_windows
from eldermind_core.services.transits import (
    aspect_orb,
    julian_day_at_noon,
    longitude_speed,
    tropical_longitude,
)

YEAR = 2027


def _jd(moment_utc: str) -> float:
    moment = datetime.strptime(moment_utc, "%Y-%m-%dT%H:%MZ")
    return julian_day_at_noon(moment.date()) + (moment.hour + moment.minute / 60.0 - 12.0) / 24.0


@pytest.fixture(scope="module")
def jupiter_point() -> dict:
    """A natal Sun exactly where Jupiter stands at noon UTC on 15 March 2027."""
    return yw.natal_point("Sun", tropical_longitude(julian_day_at_noon(date(YEAR, 3, 15)), "Jupiter"))


@pytest.fixture(scope="module")
def jupiter_windows(jupiter_point) -> list[dict]:
    return yw.aspect_spans([jupiter_point], YEAR, bodies=("Jupiter",))


def test_conjunction_window_holds_the_exact_moment(jupiter_windows):
    window = next(w for w in jupiter_windows if w["aspect"] == "Conjunction")
    assert window["start"] < "2027-03-15" < window["end"]
    assert window["exact"]
    assert any(p["exact"] and abs((date.fromisoformat(p["date"]) - date(YEAR, 3, 15)).days) <= 1
               for p in window["passes"])


def test_span_edges_sit_on_the_orb(jupiter_windows, jupiter_point):
    window = next(w for w in jupiter_windows if w["aspect"] == "Conjunction")
    for moment in (window["start_utc"], window["end_utc"]):
        orb = aspect_orb(tropical_longitude(_jd(moment), "Jupiter"), jupiter_point["longitude"], 0.0)
        assert orb == pytest.approx(yw.SPAN_ORBS["Jupiter"], abs=0.01)


def test_segments_cover_every_pass(jupiter_windows):
    for window in jupiter_windows:
        for entry in window["passes"]:
            assert any(s["start"] <= entry["date"] <= s["end"] for s in window["segments"])


def test_every_slow_pass_of_the_existing_scan_falls_in_a_span():
    sun = yw.natal_point("Sun", 123.4)
    node = yw.natal_point("TrueNode", 301.2)
    spans = yw.aspect_spans([sun, node], YEAR)
    hits = compute_transit_windows(
        [{"name": "Sun", "longitude": 123.4}, {"name": "TrueNode", "longitude": 301.2}],
        date(YEAR, 1, 1), 12, max_windows=500,
    )
    slow = [w for w in hits if w["event_type"] == "aspect" and w["transit_body"] in yw.SLOW_BODIES]
    assert slow, "the synthetic chart should have slow-planet passes in 2027"
    for window in slow:
        for entry in window["passes"]:
            if entry["date"] > "2027-12-31":
                continue
            assert any(
                s["body"] == window["transit_body"]
                and s["target"] == window["natal_body"]
                and s["aspect"] == window["aspect"]
                and s["start"] <= entry["date"] <= s["end"]
                for s in spans
            ), (window["description"], entry)


def test_arc_widens_the_span_and_gives_an_exact_range(jupiter_point):
    arc = yw.natal_point("Sun", jupiter_point["longitude"], 0.5)
    plain = next(w for w in yw.aspect_spans([jupiter_point], YEAR, bodies=("Jupiter",)) if w["aspect"] == "Conjunction")
    wide = next(w for w in yw.aspect_spans([arc], YEAR, bodies=("Jupiter",)) if w["aspect"] == "Conjunction")
    assert wide["start"] <= plain["start"] and wide["end"] >= plain["end"]
    exact = [p for p in wide["passes"] if p["exact"]]
    assert exact and all(p["exact_from"] <= p["date"] <= p["exact_to"] for p in exact)


def test_exact_ranges_never_overlap_within_a_window():
    arc = yw.natal_point("TrueNode", 310.26, 0.013)
    for window in yw.aspect_spans([arc, yw.natal_point("Sun", 54.3, 0.48)], YEAR):
        ranges = [(p["exact_from"], p["exact_to"]) for p in window["passes"] if "exact_from" in p]
        assert all(a[1] < b[0] for a, b in zip(ranges, ranges[1:])), window["id"]


def test_fast_planets_only_conjunctions_and_one_solar_return_a_year():
    spans = yw.aspect_spans([yw.natal_point("Sun", 54.3), yw.natal_point("TrueNode", 310.0)], YEAR, bodies=yw.FAST_BODIES)
    assert {w["aspect"] for w in spans} == {"Conjunction"}
    assert {w["target"] for w in spans} == {"Sun"}
    returns = [w for w in spans if w["body"] == "Sun"]
    assert len(returns) == 1 and len(returns[0]["passes"]) == 1


def test_point_range_across_aries():
    point = yw.point_range("Sun", [359.6, 359.9, 0.2, 0.4])
    assert point["half_width"] == pytest.approx(0.4)
    assert point["longitude"] == pytest.approx(0.0, abs=1e-9) or point["longitude"] == pytest.approx(360.0)


def test_mars_only_conjunction_and_opposition():
    spans = yw.aspect_spans([yw.natal_point("Sun", 10.0)], YEAR, bodies=("Mars",))
    assert spans and {w["aspect"] for w in spans} <= {"Conjunction", "Opposition"}


def test_ids_are_unique():
    spans = yw.aspect_spans([yw.natal_point("Sun", 123.4), yw.natal_point("Moon", 250.0)], YEAR)
    assert len({w["id"] for w in spans}) == len(spans)


def test_mercury_retrogrades_2027():
    found = [p for p in yw.retrograde_periods(YEAR, bodies=("Mercury",))]
    assert [(p["start"], p["end"]) for p in found] == [
        ("2027-02-09", "2027-03-03"),
        ("2027-06-10", "2027-07-04"),
        ("2027-10-07", "2027-10-28"),
    ]
    for period in found:
        middle = date.fromisoformat(period["start"]) + (date.fromisoformat(period["end"]) - date.fromisoformat(period["start"])) / 2
        assert longitude_speed(julian_day_at_noon(middle), "Mercury") < 0


def test_eclipses_2027_match_the_nasa_catalogue():
    found = yw.eclipses(YEAR)
    utc_days = [(e["kind"], e["type"], e["moment_utc"][:10]) for e in found]
    assert ("solar", "annular", "2027-02-06") in utc_days
    assert ("solar", "total", "2027-08-02") in utc_days
    assert ("lunar", "penumbral", "2027-02-20") in utc_days
    assert ("lunar", "penumbral", "2027-07-18") in utc_days
    assert ("lunar", "penumbral", "2027-08-17") in utc_days
    assert len(found) == 5


def test_eclipse_contact_with_a_point_on_the_eclipsed_sun():
    found = yw.eclipses(YEAR)
    total = next(e for e in found if e["type"] == "total")
    longitude = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
                 "Sagittarius", "Capricorn", "Aquarius", "Pisces"].index(total["sign"]) * 30 + total["degree"]
    hit = yw.eclipses(YEAR, [yw.natal_point("Moon", longitude + 2.0), yw.natal_point("Sun", longitude + 180.0)])
    contacts = next(e for e in hit if e["type"] == "total")["contacts"]
    assert {(c["target"], c["aspect"]) for c in contacts} == {("Moon", "Conjunction"), ("Sun", "Opposition")}


def test_personal_months_keep_master_numbers():
    result = yw.personal_months(date(2000, 1, 1), YEAR)  # 1 + 1 + 2027 = 2029 -> 13 -> 4
    assert result["personal_year"] == 4
    assert [m["number"] for m in result["months"]][:7] == [5, 6, 7, 8, 9, 1, 11]


def test_bazi_months_match_cnlunar():
    result = yw.bazi_months(YEAR, "甲")
    assert result["year"]["pillar"] == "丁未"
    assert result["year"]["date"] == "2027-02-04"
    assert len(result["months"]) == 13
    for month in result["months"]:
        opened = datetime.strptime(month["moment_utc"], "%Y-%m-%dT%H:%MZ") + timedelta(days=2, hours=8)
        assert cnlunar.Lunar(opened, godType="8char").month8Char == month["pillar"], month


def test_bazi_ten_gods_and_clashes():
    result = yw.bazi_months(YEAR, "甲", {"day": "丑", "year": "子"})
    assert result["year"]["stem_ten_god"].startswith("Ranny Urzędnik")  # 丁 Yin Fire from 甲 Yang Wood
    assert result["year"]["clashes"] == ["day"]  # 未 clashes 丑
    horse = next(m for m in result["months"] if m["branch"]["hanzi"] == "午")
    assert horse["clashes"] == ["year"]
    assert all(yw.BRANCH_CLASHES[yw.BRANCH_CLASHES[b]] == b for b in yw.BRANCH_CLASHES)


def test_house_periods_on_equal_houses_follow_the_signs():
    cusps = [{"house_number": n + 1, "longitude": n * 30.0} for n in range(12)]
    periods = yw.house_periods(cusps, YEAR, bodies=("Jupiter",))
    virgo = next(p for p in periods if p["house"] == 6)
    entry = date.fromisoformat(virgo["segments"][0]["start"])
    assert tropical_longitude(julian_day_at_noon(entry + timedelta(days=1)), "Jupiter") >= 150.0
    assert tropical_longitude(julian_day_at_noon(entry - timedelta(days=1)), "Jupiter") < 150.0
