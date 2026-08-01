"""Unit tests for the Human Design calculation module."""

from datetime import date, time

import pytest
import swisseph as swe

from eldermind_core.services.ephemeris import compute_julian_day_ut
from eldermind_core.services.human_design import (
    _longitude_to_gate_line,
    _sun_longitude,
    compute_human_design,
    find_design_julian_day,
)


def test_gate_start_mapping() -> None:
    """302.0° must map to Gate 41, Line 1 (HD circle start)."""
    result = _longitude_to_gate_line(302.0)
    assert result["gate"] == 41
    assert result["line"] == 1


def test_gate_sequence_known_points() -> None:
    """Verify several known gate transitions around the zodiac."""
    gate_size = 5.0 + 37.0 / 60.0 + 30.0 / 3600.0  # 5.625

    # Gate 41 spans 302.0° to 307.625°.
    assert _longitude_to_gate_line(302.0)["gate"] == 41
    assert _longitude_to_gate_line(307.624)["gate"] == 41

    # Gate 19 starts at 307.625°.
    assert _longitude_to_gate_line(307.625)["gate"] == 19

    # Gate 13 starts at 313.25°.
    assert _longitude_to_gate_line(313.25)["gate"] == 13

    # Wrap-around: 301.999° is the last sliver of gate 60.
    assert _longitude_to_gate_line(301.999)["gate"] == 60


def test_line_mapping() -> None:
    """A single gate must contain 6 lines of 0.9375 degrees each."""
    line_size = 0.0 + 56.0 / 60.0 + 15.0 / 3600.0  # 0.9375

    # Start of gate 41, first line.
    assert _longitude_to_gate_line(302.0)["line"] == 1

    # Just before the first line ends.
    assert _longitude_to_gate_line(302.0 + line_size - 0.001)["line"] == 1

    # Start of second line.
    assert _longitude_to_gate_line(302.0 + line_size)["line"] == 2

    # Last line of gate 41 starts at 302.0 + 5 * line_size.
    assert _longitude_to_gate_line(302.0 + 5 * line_size)["line"] == 6


def test_find_design_date_88_degrees_back() -> None:
    """Design Sun must be exactly 88 degrees behind Personality Sun."""
    jd_birth, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    jd_design = find_design_julian_day(jd_birth)

    birth_sun = _sun_longitude(jd_birth)
    design_sun = _sun_longitude(jd_design)

    difference = (birth_sun - design_sun) % 360.0
    assert pytest.approx(difference, abs=1e-6) == 88.0


def test_human_design_structure() -> None:
    """Human Design result must contain personality, design and design JD."""
    jd_birth, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    hd = compute_human_design(jd_birth)

    assert "design_julian_day_ut" in hd
    assert "personality" in hd
    assert "design" in hd

    assert len(hd["personality"]) == 13
    assert len(hd["design"]) == 13

    for activation in hd["personality"] + hd["design"]:
        assert 1 <= activation["gate"] <= 64
        assert 1 <= activation["line"] <= 6
        assert 0.0 <= activation["longitude"] < 360.0


def test_earth_opposite_sun() -> None:
    """Earth gate must be opposite the Sun gate in the Personality chart."""
    jd_birth, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    hd = compute_human_design(jd_birth)

    personality = {a["name"]: a for a in hd["personality"]}
    sun_gate = personality["Sun"]["gate"]
    earth_gate = personality["Earth"]["gate"]

    # Earth is 180° opposite the Sun. In HD this usually lands in the same or
    # an adjacent gate because of gate boundaries, but the longitudinal
    # separation must be close to 180°.
    sun_lon = personality["Sun"]["longitude"]
    earth_lon = personality["Earth"]["longitude"]
    separation = abs((earth_lon - sun_lon + 180.0) % 360.0 - 180.0)
    # Earth is 180° opposite the Sun; the shortest angular separation must
    # be close to 180°.
    assert pytest.approx(separation, abs=0.1) == 180.0


def test_south_node_opposite_north_node() -> None:
    """South Node longitude must be opposite North Node longitude."""
    jd_birth, _ = compute_julian_day_ut(
        date(1985, 6, 15), time(14, 30), "Europe/Warsaw"
    )
    hd = compute_human_design(jd_birth)

    personality = {a["name"]: a for a in hd["personality"]}
    north = personality["NorthNode"]["longitude"]
    south = personality["SouthNode"]["longitude"]

    separation = abs((south - north + 180.0) % 360.0 - 180.0)
    # South Node is 180° opposite the North Node.
    assert pytest.approx(separation, abs=0.1) == 180.0
