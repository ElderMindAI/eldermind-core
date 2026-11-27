"""Unit tests for the Gene Keys Hologenetic Profile module."""

from datetime import date, time

import pytest

from eldermind_core.services.ephemeris import compute_julian_day_ut
from eldermind_core.services.gene_keys import (
    ACTIVATION_SEQUENCE,
    VENUS_SEQUENCE,
    compute_gene_keys,
)
from eldermind_core.services.human_design import compute_human_design


@pytest.fixture
def sample_hd_data() -> dict:
    """Human Design data for the standard test birth date."""
    jd_birth, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    return compute_human_design(jd_birth)


def test_compute_gene_keys_structure(sample_hd_data: dict) -> None:
    """Gene Keys result must contain both sequences as dictionaries."""
    gk = compute_gene_keys(sample_hd_data)

    assert "activation_sequence" in gk
    assert "venus_sequence" in gk
    assert set(gk["activation_sequence"].keys()) == set(ACTIVATION_SEQUENCE.keys())
    assert set(gk["venus_sequence"].keys()) == set(VENUS_SEQUENCE.keys())


def test_gene_key_equals_gate(sample_hd_data: dict) -> None:
    """Every Gene Key number must match its underlying Human Design gate."""
    gk = compute_gene_keys(sample_hd_data)

    for sphere in gk["activation_sequence"].values():
        assert sphere["gene_key"] == sphere["gate"]
        assert 1 <= sphere["gene_key"] <= 64

    for sphere in gk["venus_sequence"].values():
        assert sphere["gene_key"] == sphere["gate"]
        assert 1 <= sphere["gene_key"] <= 64


def test_activation_sequence_sources(sample_hd_data: dict) -> None:
    """Activation Sequence spheres must use the correct HD activations."""
    gk = compute_gene_keys(sample_hd_data)
    activation = gk["activation_sequence"]

    assert activation["Life's Work"]["body"] == "Sun"
    assert activation["Life's Work"]["variant"] == "Personality"
    assert activation["Evolution"]["body"] == "Earth"
    assert activation["Evolution"]["variant"] == "Personality"
    assert activation["Radiance"]["body"] == "Sun"
    assert activation["Radiance"]["variant"] == "Design"
    assert activation["Purpose"]["body"] == "Earth"
    assert activation["Purpose"]["variant"] == "Design"


def test_venus_sequence_sources(sample_hd_data: dict) -> None:
    """Venus Sequence spheres must use the correct HD activations."""
    gk = compute_gene_keys(sample_hd_data)
    venus = gk["venus_sequence"]

    assert venus["Purpose"]["body"] == "Earth"
    assert venus["Purpose"]["variant"] == "Design"
    assert venus["Attraction"]["body"] == "Moon"
    assert venus["Attraction"]["variant"] == "Design"
    assert venus["IQ"]["body"] == "Venus"
    assert venus["IQ"]["variant"] == "Personality"
    assert venus["EQ"]["body"] == "Mars"
    assert venus["EQ"]["variant"] == "Personality"
    assert venus["SQ"]["body"] == "Venus"
    assert venus["SQ"]["variant"] == "Design"
    assert venus["Core Wound"]["body"] == "Mars"
    assert venus["Core Wound"]["variant"] == "Design"


def test_pearl_sequence_sources(sample_hd_data: dict) -> None:
    """Pearl Sequence spheres must use the correct HD activations."""
    gk = compute_gene_keys(sample_hd_data)
    pearl = gk["pearl_sequence"]

    assert pearl["Vocation"]["body"] == "Mars"
    assert pearl["Vocation"]["variant"] == "Design"
    assert pearl["Culture"]["body"] == "Jupiter"
    assert pearl["Culture"]["variant"] == "Design"
    assert pearl["Brand"]["body"] == "Sun"
    assert pearl["Brand"]["variant"] == "Personality"
    assert pearl["Pearl"]["body"] == "Jupiter"
    assert pearl["Pearl"]["variant"] == "Personality"


def test_gene_keys_consistency_with_human_design(sample_hd_data: dict) -> None:
    """Gene Key longitudes and lines must match the underlying HD activation."""
    gk = compute_gene_keys(sample_hd_data)

    personality = {a["name"]: a for a in sample_hd_data["personality"]}
    design = {a["name"]: a for a in sample_hd_data["design"]}

    life_work = gk["activation_sequence"]["Life's Work"]
    assert life_work["gate"] == personality["Sun"]["gate"]
    assert life_work["line"] == personality["Sun"]["line"]
    assert life_work["longitude"] == pytest.approx(personality["Sun"]["longitude"])

    radiance = gk["activation_sequence"]["Radiance"]
    assert radiance["gate"] == design["Sun"]["gate"]
    assert radiance["line"] == design["Sun"]["line"]
    assert radiance["longitude"] == pytest.approx(design["Sun"]["longitude"])

    eq = gk["venus_sequence"]["EQ"]
    assert (eq["gate"], eq["line"]) == (personality["Mars"]["gate"], personality["Mars"]["line"])
    core = gk["venus_sequence"]["Core Wound"]
    assert (core["gate"], core["line"]) == (design["Mars"]["gate"], design["Mars"]["line"])
    assert gk["pearl_sequence"]["Vocation"] == {**core, "sphere": "Vocation", "sequence": "Pearl"}


# Every sphere's source as listed by the Gene Keys FAQ "What planets does each
# Sphere of the Golden Path Profile correlate to?" (genekeys.com, 2024-12-15):
# natal = Personality, pre-natal = Design.
STANDARD_SOURCES = {
    "Life's Work": ("Personality", "Sun"),
    "Evolution": ("Personality", "Earth"),
    "Radiance": ("Design", "Sun"),
    "Purpose": ("Design", "Earth"),
    "Attraction": ("Design", "Moon"),
    "IQ": ("Personality", "Venus"),
    "EQ": ("Personality", "Mars"),
    "SQ": ("Design", "Venus"),
    "Core Wound": ("Design", "Mars"),
    "Vocation": ("Design", "Mars"),
    "Culture": ("Design", "Jupiter"),
    "Brand": ("Personality", "Sun"),
    "Pearl": ("Personality", "Jupiter"),
}


def test_every_sphere_matches_the_standard(sample_hd_data: dict) -> None:
    """All 13 sphere slots (11 distinct spheres) follow the published mapping."""
    gk = compute_gene_keys(sample_hd_data)
    seen = {}
    for seq in ("activation_sequence", "venus_sequence", "pearl_sequence"):
        for name, sphere in gk[seq].items():
            seen[name] = (sphere["variant"], sphere["body"])
    assert seen == STANDARD_SOURCES


# Two reference profiles read off published Hologenetic Profile charts
# (gene key.line). Bare dates, a synthetic place (49.7497 N, 18.6354 E).
@pytest.mark.parametrize(
    ("birth_date", "birth_time", "eq", "core"),
    [
        (date(1999, 7, 24), time(18, 10), (44, 1), (28, 3)),
        (date(1993, 10, 13), time(10, 0), (44, 4), (64, 2)),
    ],
)
def test_eq_and_core_against_reference_charts(birth_date, birth_time, eq, core) -> None:
    jd_birth, _ = compute_julian_day_ut(birth_date, birth_time, "Europe/Warsaw")
    gk = compute_gene_keys(compute_human_design(jd_birth))
    got_eq = gk["venus_sequence"]["EQ"]
    got_core = gk["venus_sequence"]["Core Wound"]
    got_vocation = gk["pearl_sequence"]["Vocation"]
    assert (got_eq["gene_key"], got_eq["line"]) == eq
    assert (got_core["gene_key"], got_core["line"]) == core
    assert (got_vocation["gene_key"], got_vocation["line"]) == core
