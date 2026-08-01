"""Tests for the detail levels (bloker B6).

The thing worth guarding here is not the byte count but the *content*: a summary
full of nulls would pass a size check and be useless to a model. So these tests
assert that the fields a reader actually needs are present and correct, and only
then that the payload got smaller.
"""

from __future__ import annotations

import json
from datetime import date, time

import pytest

from eldermind_core.detail import DETAIL_LEVELS, apply_detail
from eldermind_core.profile import Subject, compute_profile

SUBJECT = Subject(
    birth_date=date(1993, 9, 1),
    latitude=52.2297,
    longitude=21.0122,
    timezone="Europe/Warsaw",
    birth_time=time(14, 30),
    gender="male",
    full_name="Marcin Jan Kowalski",
    reference_date=date(2026, 7, 31),
)


@pytest.fixture(scope="module")
def payload() -> dict:
    return compute_profile(SUBJECT).to_dict()


def _size(data: dict) -> int:
    return len(json.dumps(data, ensure_ascii=False))


def test_summary_is_dramatically_smaller_than_full(payload: dict) -> None:
    """The whole point of B6: one tool call must not eat the model's context."""
    summary = _size(apply_detail(payload, "summary"))
    full = _size(apply_detail(payload, "full"))
    assert summary < full / 5, f"summary {summary} B is not much smaller than full {full} B"


def test_levels_are_ordered_by_size(payload: dict) -> None:
    sizes = [_size(apply_detail(payload, level)) for level in DETAIL_LEVELS]
    assert sizes == sorted(sizes)


def test_full_is_returned_untouched(payload: dict) -> None:
    assert apply_detail(payload, "full") is payload


def test_unknown_level_falls_back_to_standard(payload: dict) -> None:
    """A client on a newer API version should get data, not a 400."""
    assert _size(apply_detail(payload, "ultra")) == _size(apply_detail(payload, "standard"))


def test_summary_has_no_empty_fields(payload: dict) -> None:
    """A summary of nulls would pass a size check and help nobody."""
    summary = apply_detail(payload, "summary")
    empty = [
        f"{system}.{field}"
        for system, data in summary.items()
        if system != "meta" and isinstance(data, dict)
        for field, value in data.items()
        if value is None
    ]
    assert not empty, f"summary has empty fields: {empty}"


def test_summary_uses_readable_names_not_codes(payload: dict) -> None:
    """DX rule from the plan: the model must understand it without a lookup table."""
    human_design = apply_detail(payload, "summary")["human_design"]
    assert human_design["type"] == "Manifesting Generator"
    assert human_design["profile"] == "4/6"

    bazi = apply_detail(payload, "summary")["bazi"]
    assert bazi["day_master"] == "Yi (Yin Wood)"
    assert bazi["year_pillar"]["branch"] == "Rooster (Yin Metal)"


def test_summary_moon_sign_is_the_moons_not_the_ascendants(payload: dict) -> None:
    """Regression guard: a naive fallback reports the Ascendant's sign instead.

    The Moon sits in Shatabhisha, which lies in Aquarius. Scorpio is the
    Ascendant — the wrong answer this test exists to catch.
    """
    vedic = apply_detail(payload, "summary")["vedic"]
    assert vedic["moon_nakshatra"] == "Shatabhisha"
    assert vedic["moon_sign"] == "Aquarius"
    assert vedic["ascendant_sign"] == "Scorpio"


def test_summary_keeps_the_conclusions_a_reader_asks_for(payload: dict) -> None:
    summary = apply_detail(payload, "summary")

    assert summary["vedic"]["current_mahadasha"]["lord"] == "Saturn"
    assert summary["vedic"]["sade_sati"]["status"] in {"active", "inactive"}
    assert summary["gene_keys"]["activation_sequence"]["Life's Work"] == "40.4"
    assert summary["western"]["sun"].startswith("Virgo")
    assert summary["numerology"]["life_path"] == payload["numerology"]["life_path"]


def test_standard_drops_history_but_keeps_positions(payload: dict) -> None:
    standard = apply_detail(payload, "standard")

    # The 100-year Dasha table and the ten-year luck pillars are export-only.
    assert "timeline" not in standard["vedic"]["vimshottari_dasha"]
    assert "da_yun" not in standard["bazi"]
    # ...but every position stays.
    assert len(standard["western"]["planets"]) == 11
    assert len(standard["vedic"]["houses"]) == 12
    assert standard["human_design"]["mechanics"]["type"] == "Manifesting Generator"


def test_projection_does_not_mutate_the_source(payload: dict) -> None:
    """One computed profile must serve every level — that is what makes it cacheable."""
    before = _size(payload)
    apply_detail(payload, "summary")
    apply_detail(payload, "standard")
    assert _size(payload) == before
