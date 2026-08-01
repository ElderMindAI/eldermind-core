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
    assert venus["EQ"]["variant"] == "Design"
    assert venus["SQ"]["body"] == "Venus"
    assert venus["SQ"]["variant"] == "Design"
    assert venus["Core Wound"]["body"] == "Mars"
    assert venus["Core Wound"]["variant"] == "Personality"


def test_pearl_sequence_sources(sample_hd_data: dict) -> None:
    """Pearl Sequence spheres must use the correct HD activations."""
    gk = compute_gene_keys(sample_hd_data)
    pearl = gk["pearl_sequence"]

    assert pearl["Vocation"]["body"] == "Mars"
    assert pearl["Vocation"]["variant"] == "Personality"
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
