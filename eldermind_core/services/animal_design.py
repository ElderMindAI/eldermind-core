"""Animal Design ("Mammalian Design System") calculation engine.

Mirrors the structure of `eldermind_core.services.human_design` but for the simplified
15-gate animal system: same underlying 64-gate wheel geometry (reused via
`longitude_to_gate_line`), same standard body list (Sun/Moon/planets/Nodes),
but with two key differences:

1. The "Design" (unconscious) moment is found via the MOON going 88 degrees
   back (~6-7 days before birth) instead of the Sun (~88 days) — see
   `find_animal_design_julian_day()`.
2. Only activations whose gate falls within the 15 mammalian gates
   (`ANIMAL_GATES`) are kept; everything else is discarded.

Deliberately does NOT import/modify anything in `eldermind_core.core.hd_constants` or
mutate the human HD engine — kept fully separate per product requirements.
"""

from __future__ import annotations

from datetime import date, time

import swisseph as swe

from eldermind_core.core.animal_design_constants import (
    ANIMAL_CENTERS,
    ANIMAL_CHANNELS,
    ANIMAL_CROSS_SPECIES_PORTALS,
    ANIMAL_GATE_TO_CENTER,
    ANIMAL_GATES,
    ANIMAL_GROUPS,
    ANIMAL_MOTOR_CENTERS,
)
from eldermind_core.core.hd_constants import HD_BODY_IDS
from eldermind_core.services.ephemeris import _local_to_utc, _utc_to_julian_day_ut, compute_planet_position
from eldermind_core.services.human_design import longitude_to_gate_line


def _moon_longitude(jd_ut: float) -> float:
    """Return the tropical longitude of the Moon at a given Julian Day."""
    result, err = swe.calc_ut(jd_ut, swe.MOON, 0)
    if err and not result:
        raise RuntimeError(f"Failed to compute Moon position: {err}")
    return float(result[0]) % 360.0


def _moon_position_error(jd_ut: float, target_longitude: float) -> float:
    """Difference between the Moon's longitude at jd_ut and the target,
    wrapped to [-180, 180] for stable root finding."""
    current = _moon_longitude(jd_ut)
    delta = (current - target_longitude + 180.0) % 360.0 - 180.0
    return delta


def find_animal_design_julian_day(jd_birth_ut: float, max_iterations: int = 50) -> float:
    """Find the Julian Day when the Moon was exactly 88 degrees back.

    Analogous to `human_design.find_design_julian_day()`, but rooting on the
    Moon's tropical longitude instead of the Sun's — the animal system's
    "Design" moment is roughly 6-7 days before birth, not ~88 days.
    """
    target_moon_longitude = (_moon_longitude(jd_birth_ut) - 88.0) % 360.0
    # Initial guess: the Moon moves ~13°/day, so 88° back is ~6.75 days earlier.
    jd_design = jd_birth_ut - 6.75

    for _ in range(max_iterations):
        error = _moon_position_error(jd_design, target_moon_longitude)
        if abs(error) < 1e-7:
            break

        epsilon = 1.0 / 86400.0  # one second in days
        speed = (
            _moon_position_error(jd_design + epsilon, target_moon_longitude)
            - _moon_position_error(jd_design - epsilon, target_moon_longitude)
        ) / (2.0 * epsilon)

        if abs(speed) < 1e-12:
            raise RuntimeError("Moon longitude derivative is too small; cannot converge")

        jd_design -= error / speed
    else:
        raise RuntimeError(
            f"Animal Design date search did not converge within {max_iterations} iterations"
        )

    return jd_design


def _compute_body_activation(
    jd_ut: float,
    name: str,
    planet_id: int,
    *,
    offset_degrees: float = 0.0,
) -> dict:
    """Compute gate/line activation for a single body, reusing the same
    64-gate wheel as the human HD engine (`longitude_to_gate_line`)."""
    longitude = compute_planet_position(jd_ut, name, planet_id)["longitude"]
    longitude = (longitude + offset_degrees) % 360.0
    result = longitude_to_gate_line(longitude)
    result["name"] = name
    return result


def _filter_to_animal_gates(activations: list[dict]) -> list[dict]:
    """Discard every activation whose gate isn't one of the 15 mammalian gates."""
    return [a for a in activations if int(a["gate"]) in ANIMAL_GATES]


def _defined_channels(activated_gates: set[int]) -> list[dict]:
    """Return the animal channels whose *both* gates are activated."""
    channels: list[dict] = []
    for gate_a, gate_b in ANIMAL_CHANNELS:
        if gate_a in activated_gates and gate_b in activated_gates:
            center_a = ANIMAL_GATE_TO_CENTER[gate_a]
            center_b = ANIMAL_GATE_TO_CENTER[gate_b]
            channels.append(
                {
                    "id": f"{gate_a}-{gate_b}",
                    "gates": [gate_a, gate_b],
                    "centers": sorted({center_a, center_b}),
                }
            )
    return channels


def _connected_components(defined_centers: set[str], channels: list[dict]) -> list[set[str]]:
    """Group defined centers into connected components via defined channels
    (union-find), same algorithm as the human HD engine."""
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


def _determine_type(defined_centers: set[str]) -> str:
    """Simplified animal Type: only 3 buckets, matching what the source
    material actually documents (no invented Manifestor/Projector analogs).
    """
    if not defined_centers:
        return "Reflector"
    if "Sacral" in defined_centers:
        return "Generator"
    return "Defined"


def _determine_authority(defined_centers: set[str]) -> str:
    """Simplified animal Authority hierarchy (no SolarPlexus/Heart exist in
    this system): Sacral > Splenic > Self-Projected (G) > Lunar (Reflector).
    """
    if "Sacral" in defined_centers:
        return "Sacral"
    if "Spleen" in defined_centers:
        return "Splenic"
    if "G" in defined_centers:
        return "Self-Projected"
    return "Lunar"


def _active_groups(activated_gates: set[int]) -> list[dict]:
    """Which of the 3 groups (Territory/Metamorphosis/Alpha) have at least
    one activated gate, and whether their Portal Gate specifically is active.
    """
    groups: list[dict] = []
    for group_name, group_data in ANIMAL_GROUPS.items():
        active_gates = sorted(g for g in group_data["gates"] if g in activated_gates)
        if not active_gates:
            continue
        groups.append(
            {
                "name": group_name,
                "active_gates": active_gates,
                "portal_gate_active": group_data["portal_gate"] in activated_gates,
            }
        )
    return groups


def _active_portals(activated_gates: set[int]) -> list[dict]:
    """Which of the 3 Cross-Species Portal Gates are active."""
    portals: list[dict] = []
    for gate, info in ANIMAL_CROSS_SPECIES_PORTALS.items():
        if gate in activated_gates:
            portals.append({"animal_gate": gate, **info})
    return portals


def compute_animal_design_mechanics(personality: list[dict], design: list[dict]) -> dict:
    """Derive the animal body-graph mechanics from raw (already-filtered)
    Personality + Design activations."""
    activated_gates: set[int] = {int(b["gate"]) for b in personality} | {
        int(b["gate"]) for b in design
    }

    channels = _defined_channels(activated_gates)
    defined_centers: set[str] = set()
    for channel in channels:
        defined_centers.update(channel["centers"])
    open_centers = [c for c in ANIMAL_CENTERS if c not in defined_centers]

    components = _connected_components(defined_centers, channels)

    animal_type = _determine_type(defined_centers)
    authority = _determine_authority(defined_centers)

    definition_map = {
        0: "No Definition",
        1: "Single Definition",
        2: "Split Definition",
        3: "Triple Split Definition",
    }
    definition = definition_map.get(len(components), "No Definition")

    gates_by_center: dict[str, list[int]] = {center: [] for center in ANIMAL_CENTERS}
    for gate in sorted(activated_gates):
        gates_by_center[ANIMAL_GATE_TO_CENTER[gate]].append(gate)

    return {
        "type": animal_type,
        "authority": authority,
        "definition": definition,
        "defined_centers": [c for c in ANIMAL_CENTERS if c in defined_centers],
        "open_centers": open_centers,
        "channels": channels,
        "gates_by_center": gates_by_center,
        "activated_gates": sorted(activated_gates),
        "groups": _active_groups(activated_gates),
        "portals": _active_portals(activated_gates),
    }


def compute_animal_design(jd_birth_ut: float) -> dict:
    """Calculate the animal's Personality + Design activations (already
    filtered to the 15 mammalian gates) and derive the full mechanics.
    """
    jd_design_ut = find_animal_design_julian_day(jd_birth_ut)

    personality_raw: list[dict] = []
    design_raw: list[dict] = []

    for name, planet_id in HD_BODY_IDS.items():
        offset = 180.0 if name in ("Earth", "SouthNode") else 0.0
        personality_raw.append(
            _compute_body_activation(jd_birth_ut, name, planet_id, offset_degrees=offset)
        )
        design_raw.append(
            _compute_body_activation(jd_design_ut, name, planet_id, offset_degrees=offset)
        )

    personality = _filter_to_animal_gates(personality_raw)
    design = _filter_to_animal_gates(design_raw)

    mechanics = compute_animal_design_mechanics(personality, design)

    return {
        "design_julian_day_ut": round(jd_design_ut, 8),
        "personality": personality,
        "design": design,
        "mechanics": mechanics,
    }


def compute_animal_design_from_birth(
    birth_date: date,
    birth_time: time,
    timezone_name: str,
) -> dict:
    """Convenience wrapper that accepts local birth data."""
    utc_dt = _local_to_utc(birth_date, birth_time, timezone_name)
    jd_birth_ut = _utc_to_julian_day_ut(utc_dt)
    return compute_animal_design(jd_birth_ut)
