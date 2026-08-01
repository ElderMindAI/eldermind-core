"""Human Design calculation module.

Computes Personality (natal) and Design (Sun 88 degrees back) activations
for the standard HD body list and maps tropical longitudes to Human Design
gates and lines.
"""

from datetime import date, datetime
from typing import Tuple

import swisseph as swe

from eldermind_core.core.hd_constants import (
    HD_BODY_IDS,
    HD_CENTERS,
    HD_CHANNELS,
    HD_CROSS_ANGLE_BY_PROFILE,
    HD_GATE_COUNT,
    HD_GATE_DEGREES,
    HD_GATE_SEQUENCE,
    HD_GATE_START_DEGREES,
    HD_GATE_TO_CENTER,
    HD_LINE_COUNT,
    HD_LINE_DEGREES,
    HD_MOTOR_CENTERS,
    HD_TYPE_INFO,
)
from eldermind_core.services.ephemeris import _utc_to_julian_day_ut, compute_planet_position


def longitude_to_gate_line(longitude: float) -> dict:
    """Map a tropical longitude to a Human Design gate and line.

    The HD circle begins at 02° Aquarius (302.0°). Each gate spans 5.625°
    and each gate contains 6 lines of 0.9375° each.

    Args:
        longitude: Tropical ecliptic longitude in degrees [0, 360).

    Returns:
        Dictionary with gate (1-64), line (1-6) and the raw longitude.
    """
    normalized = longitude % 360.0
    # Offset from the HD starting point, wrapped to [0, 360).
    offset = (normalized - HD_GATE_START_DEGREES) % 360.0

    gate_index = int(offset // HD_GATE_DEGREES) % HD_GATE_COUNT
    gate = HD_GATE_SEQUENCE[gate_index]

    line_offset = offset - (gate_index * HD_GATE_DEGREES)
    line = (int(line_offset // HD_LINE_DEGREES) % HD_LINE_COUNT) + 1

    return {
        "longitude": round(longitude, 6),
        "gate": gate,
        "line": line,
    }


# Backward-compatible private alias.
_longitude_to_gate_line = longitude_to_gate_line


def _sun_longitude(jd_ut: float) -> float:
    """Return the tropical longitude of the Sun at a given Julian Day."""
    result, err = swe.calc_ut(jd_ut, swe.SUN, 0)
    if err and not result:
        raise RuntimeError(f"Failed to compute Sun position: {err}")
    return float(result[0]) % 360.0


def _sun_position_error(jd_ut: float, target_longitude: float) -> float:
    """Difference between the Sun's longitude at jd_ut and the target.

    The result is wrapped to [-180, 180] for stable root finding.
    """
    current = _sun_longitude(jd_ut)
    delta = (current - target_longitude + 180.0) % 360.0 - 180.0
    return delta


def find_design_julian_day(jd_birth_ut: float, max_iterations: int = 50) -> float:
    """Find the Julian Day when the Sun was exactly 88 degrees back.

    This is not a fixed 88-day offset; the Sun's apparent motion varies.
    We use a Newton-Raphson search on the Sun's tropical longitude.

    Args:
        jd_birth_ut: Julian Day UT of the birth moment (Personality).
        max_iterations: Safety limit for the root-finding loop.

    Returns:
        Julian Day UT of the Design moment.
    """
    target_sun_longitude = (_sun_longitude(jd_birth_ut) - 88.0) % 360.0
    # Initial guess: roughly 87-89 days earlier (Sun moves ~1°/day).
    jd_design = jd_birth_ut - 88.0

    for _ in range(max_iterations):
        error = _sun_position_error(jd_design, target_sun_longitude)
        if abs(error) < 1e-7:  # sub-arc-second precision
            break

        # Numerical derivative of Sun longitude with respect to time.
        epsilon = 1.0 / 86400.0  # one second in days
        speed = (
            _sun_position_error(jd_design + epsilon, target_sun_longitude)
            - _sun_position_error(jd_design - epsilon, target_sun_longitude)
        ) / (2.0 * epsilon)

        if abs(speed) < 1e-12:
            raise RuntimeError("Sun longitude derivative is too small; cannot converge")

        jd_design -= error / speed
    else:
        raise RuntimeError(
            f"Design date search did not converge within {max_iterations} iterations"
        )

    return jd_design


def _compute_hd_body(
    jd_ut: float,
    name: str,
    planet_id: int,
    *,
    offset_degrees: float = 0.0,
) -> dict:
    """Compute gate/line activation for a single HD body.

    Args:
        jd_ut: Julian Day UT.
        name: Canonical body name.
        planet_id: pyswisseph identifier.
        offset_degrees: Optional longitudinal offset (e.g. 180° for Earth/anti-node).

    Returns:
        Dictionary with name, longitude, gate and line.
    """
    longitude = compute_planet_position(jd_ut, name, planet_id)["longitude"]
    longitude = (longitude + offset_degrees) % 360.0

    result = _longitude_to_gate_line(longitude)
    result["name"] = name
    return result


def _defined_channels(activated_gates: set[int]) -> list[dict]:
    """Return the channels whose *both* gates are activated.

    A channel defines its two centers only when it is fully formed, i.e. both
    of its gates are present in the activation set (a single hanging gate does
    not define a center).

    Args:
        activated_gates: Set of all activated gate numbers (Personality + Design).

    Returns:
        List of channel dictionaries with id, gates and connected centers.
    """
    channels: list[dict] = []
    for gate_a, gate_b in HD_CHANNELS:
        if gate_a in activated_gates and gate_b in activated_gates:
            center_a = HD_GATE_TO_CENTER[gate_a]
            center_b = HD_GATE_TO_CENTER[gate_b]
            channels.append(
                {
                    "id": f"{gate_a}-{gate_b}",
                    "gates": [gate_a, gate_b],
                    "centers": sorted({center_a, center_b}),
                }
            )
    return channels


def _connected_components(
    defined_centers: set[str], channels: list[dict]
) -> list[set[str]]:
    """Group defined centers into connected components via defined channels.

    Uses a simple union-find over the graph where nodes are defined centers
    and edges are the channels connecting them. The number of components maps
    directly to the HD Definition (Single, Split, Triple Split, ...).

    Args:
        defined_centers: Set of centers that carry at least one defined channel.
        channels: List of defined channel dictionaries.

    Returns:
        List of center-sets, one per connected component.
    """
    parent: dict[str, str] = {center: center for center in defined_centers}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for channel in channels:
        centers = channel["centers"]
        if len(centers) == 2:
            union(centers[0], centers[1])

    groups: dict[str, set[str]] = {}
    for center in defined_centers:
        root = find(center)
        groups.setdefault(root, set()).add(center)
    return list(groups.values())


def _motor_connected_to_throat(
    defined_centers: set[str], components: list[set[str]]
) -> bool:
    """True if any motor center shares a defined component with the Throat."""
    if "Throat" not in defined_centers:
        return False
    for component in components:
        if "Throat" in component and (HD_MOTOR_CENTERS & component):
            return True
    return False


def _determine_type(
    defined_centers: set[str], motor_to_throat: bool
) -> str:
    """Derive the HD Type from the defined centers and motor-to-throat link."""
    if not defined_centers:
        return "Reflector"
    if "Sacral" in defined_centers:
        return "Manifesting Generator" if motor_to_throat else "Generator"
    # Sacral undefined.
    if motor_to_throat:
        return "Manifestor"
    return "Projector"


def _determine_authority(hd_type: str, defined_centers: set[str]) -> str:
    """Derive the Inner Authority using the standard HD hierarchy."""
    if hd_type == "Reflector":
        return "Lunar"
    if "SolarPlexus" in defined_centers:
        return "Emotional (Solar Plexus)"
    if "Sacral" in defined_centers:
        return "Sacral"
    if "Spleen" in defined_centers:
        return "Splenic"
    if "Heart" in defined_centers:
        return "Ego (Heart)"
    if "G" in defined_centers:
        return "Self-Projected"
    return "Mental (Environmental)"


def _sun_line(activations: list[dict]) -> int:
    """Return the line of the Sun activation from an activation list."""
    for body in activations:
        if body["name"] == "Sun":
            return int(body["line"])
    raise ValueError("Sun activation not found")


def _body_gate(activations: list[dict], body_name: str) -> int:
    """Return the gate of a named body from an activation list."""
    for body in activations:
        if body["name"] == body_name:
            return int(body["gate"])
    raise ValueError(f"{body_name} activation not found")


def compute_hd_mechanics(personality: list[dict], design: list[dict]) -> dict:
    """Derive the full body-graph mechanics from raw activations.

    Computes Type, Strategy, Authority, Profile, Definition, Incarnation Cross
    (gates + angle), defined/open centers, defined channels and gates grouped
    by center. All values are deterministic; interpretive meanings are supplied
    later by the RAG knowledge base.

    Args:
        personality: Personality (conscious) activation list.
        design: Design (unconscious) activation list.

    Returns:
        Mechanics dictionary matching the ``HDMechanics`` schema.
    """
    activated_gates: set[int] = {int(b["gate"]) for b in personality} | {
        int(b["gate"]) for b in design
    }

    channels = _defined_channels(activated_gates)
    defined_centers: set[str] = set()
    for channel in channels:
        defined_centers.update(channel["centers"])
    open_centers = [c for c in HD_CENTERS if c not in defined_centers]

    components = _connected_components(defined_centers, channels)
    motor_to_throat = _motor_connected_to_throat(defined_centers, components)

    hd_type = _determine_type(defined_centers, motor_to_throat)
    authority = _determine_authority(hd_type, defined_centers)
    type_info = HD_TYPE_INFO[hd_type]

    conscious_line = _sun_line(personality)
    unconscious_line = _sun_line(design)
    profile = f"{conscious_line}/{unconscious_line}"

    definition_map = {
        0: "No Definition",
        1: "Single Definition",
        2: "Split Definition",
        3: "Triple Split Definition",
        4: "Quadruple Split Definition",
    }
    definition = definition_map.get(len(components), "No Definition")

    cross_gates = [
        _body_gate(personality, "Sun"),
        _body_gate(personality, "Earth"),
        _body_gate(design, "Sun"),
        _body_gate(design, "Earth"),
    ]
    cross_angle = HD_CROSS_ANGLE_BY_PROFILE.get(profile, "Right Angle")

    gates_by_center: dict[str, list[int]] = {center: [] for center in HD_CENTERS}
    for gate in sorted(activated_gates):
        gates_by_center[HD_GATE_TO_CENTER[gate]].append(gate)

    return {
        "type": hd_type,
        "strategy": type_info["strategy"],
        "signature": type_info["signature"],
        "not_self_theme": type_info["not_self_theme"],
        "authority": authority,
        "profile": profile,
        "definition": definition,
        "incarnation_cross_gates": cross_gates,
        "incarnation_cross_angle": cross_angle,
        "defined_centers": [c for c in HD_CENTERS if c in defined_centers],
        "open_centers": open_centers,
        "channels": channels,
        "gates_by_center": gates_by_center,
    }


def compute_human_design(jd_birth_ut: float) -> dict:
    """Calculate Personality and Design activations for Human Design.

    Args:
        jd_birth_ut: Julian Day UT of the birth moment.

    Returns:
        Dictionary with personality and design activation lists, the design
        Julian Day and the fully derived body-graph mechanics.
    """
    jd_design_ut = find_design_julian_day(jd_birth_ut)

    personality: list[dict] = []
    design: list[dict] = []

    for name, planet_id in HD_BODY_IDS.items():
        offset = 180.0 if name in ("Earth", "SouthNode") else 0.0
        personality.append(_compute_hd_body(jd_birth_ut, name, planet_id, offset_degrees=offset))
        design.append(_compute_hd_body(jd_design_ut, name, planet_id, offset_degrees=offset))

    mechanics = compute_hd_mechanics(personality, design)

    return {
        "design_julian_day_ut": round(jd_design_ut, 8),
        "personality": personality,
        "design": design,
        "mechanics": mechanics,
    }


def compute_human_design_from_birth(
    birth_date: date,
    birth_time: datetime.time,
    timezone_name: str,
) -> dict:
    """Convenience wrapper that accepts local birth data.

    Args:
        birth_date: Local birth date.
        birth_time: Local birth time.
        timezone_name: IANA timezone name.

    Returns:
        Human Design result dictionary.
    """
    from eldermind_core.services.ephemeris import _local_to_utc

    utc_dt = _local_to_utc(birth_date, birth_time, timezone_name)
    jd_birth_ut = _utc_to_julian_day_ut(utc_dt)
    return compute_human_design(jd_birth_ut)
