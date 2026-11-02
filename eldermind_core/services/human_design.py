"""Human Design calculation module.

Computes Personality (natal) and Design (Sun 88 degrees back) activations
for the standard HD body list and maps tropical longitudes to Human Design
gates and lines.
"""

from datetime import date, datetime
from typing import Final, Tuple

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


def _split_bridges(
    activated_gates: set[int], components: list[set[str]]
) -> dict | None:
    """What would join the separate parts of a split definition.

    `single_gate`: a gate the chart lacks that, together with one of its own
    gates, completes a channel between two different defined components.
    `channel_pairs`: channels between two components with neither gate
    present. Bridges through an undefined center (two channels or more) are
    not listed. Until 1.0.4 the model counted these itself and got them
    wrong in three reports out of three (2026-11-02).

    Returns None for a chart with fewer than two components.
    """
    if len(components) < 2:
        return None
    # Set iteration order is not stable across processes; the golden files are.
    components = sorted(components, key=lambda part: min(HD_CENTERS.index(c) for c in part))
    component_of = {
        center: index for index, component in enumerate(components) for center in component
    }

    single_gate: list[dict] = []
    channel_pairs: list[dict] = []
    for gate_a, gate_b in HD_CHANNELS:
        center_a, center_b = HD_GATE_TO_CENTER[gate_a], HD_GATE_TO_CENTER[gate_b]
        if center_a not in component_of or center_b not in component_of:
            continue
        if component_of[center_a] == component_of[center_b]:
            continue
        has_a, has_b = gate_a in activated_gates, gate_b in activated_gates
        channel = f"{gate_a}-{gate_b}"
        if has_a and has_b:
            continue  # already defined, so the centers would share a component
        if has_a or has_b:
            missing, natal = (gate_b, gate_a) if has_a else (gate_a, gate_b)
            single_gate.append(
                {
                    "gate": missing,
                    "with_natal_gate": natal,
                    "channel": channel,
                    "connects": [HD_GATE_TO_CENTER[natal], HD_GATE_TO_CENTER[missing]],
                }
            )
        else:
            channel_pairs.append(
                {"channel": channel, "gates": [gate_a, gate_b], "connects": [center_a, center_b]}
            )

    return {
        "components": [
            [center for center in HD_CENTERS if center in component] for component in components
        ],
        "single_gate": sorted(single_gate, key=lambda item: (item["gate"], item["with_natal_gate"])),
        "channel_pairs": channel_pairs,
    }


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
        "split_bridges": _split_bridges(activated_gates, components),
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


# Transiting bodies Human Design reads besides the planets: the Earth opposite
# the Sun and the South Node opposite the North (true) node.
_OPPOSITE_BODIES: Final[dict[str, str]] = {"Earth": "Sun", "SouthNode": "TrueNode"}

# Scan step and search horizon, in days, for the edges of a body's stay in one
# gate. Generous for the slow bodies: a station can hold Pluto in a gate for years.
_GATE_SCAN: Final[dict[str, tuple[float, float]]] = {
    "Moon": (1.0 / 24.0, 3.0),
    "Sun": (0.25, 12.0),
    "Earth": (0.25, 12.0),
    "Mercury": (0.5, 200.0),
    "Venus": (0.5, 200.0),
    "Mars": (0.5, 320.0),
    "Jupiter": (1.0, 800.0),
    "Saturn": (1.0, 1200.0),
    "TrueNode": (1.0, 700.0),
    "SouthNode": (1.0, 700.0),
    "Uranus": (2.0, 2600.0),
    "Neptune": (2.0, 2600.0),
    "Pluto": (2.0, 2600.0),
}

_PLANET_IDS_BY_NAME: Final[dict[str, int]] = {
    "Sun": 0, "Earth": 0, "Moon": 1, "Mercury": 2, "Venus": 3, "Mars": 4,
    "Jupiter": 5, "Saturn": 6, "Uranus": 7, "Neptune": 8, "Pluto": 9,
    "TrueNode": 11, "SouthNode": 11,
}


def _gate_of(jd_ut: float, planet_id: int, offset: float) -> int:
    result, _ = swe.calc_ut(jd_ut, planet_id, 0)
    return longitude_to_gate_line((float(result[0]) + offset) % 360.0)["gate"]


def _gate_edge(
    jd_ut: float, planet_id: int, offset: float, gate: int, step: float, horizon: float, forward: bool
) -> float | None:
    """Moment the body leaves `gate` going forward (or entered it, going back)."""
    direction = 1.0 if forward else -1.0
    inside = jd_ut
    travelled = 0.0
    while travelled < horizon:
        probe = inside + direction * step
        if _gate_of(probe, planet_id, offset) != gate:
            outside = probe
            for _ in range(40):
                middle = (inside + outside) / 2.0
                if _gate_of(middle, planet_id, offset) == gate:
                    inside = middle
                else:
                    outside = middle
                if abs(outside - inside) < 1.0 / 1440.0:
                    break
            return (inside + outside) / 2.0
        inside = probe
        travelled += step
    return None


def _jd_to_iso(jd_ut: float | None) -> str | None:
    if jd_ut is None:
        return None
    year, month, day, _ = swe.revjul(jd_ut)
    return date(int(year), int(month), int(day)).isoformat()


def transit_gate_window(body: str, jd_ut: float) -> dict:
    """When a transiting body entered its current gate and when it leaves it."""
    planet_id = _PLANET_IDS_BY_NAME[body]
    offset = 180.0 if body in _OPPOSITE_BODIES else 0.0
    step, horizon = _GATE_SCAN[body]
    gate = _gate_of(jd_ut, planet_id, offset)
    start = _gate_edge(jd_ut, planet_id, offset, gate, step, horizon, forward=False)
    end = _gate_edge(jd_ut, planet_id, offset, gate, step, horizon, forward=True)
    return {
        "active_from": _jd_to_iso(start),
        "active_until": _jd_to_iso(end),
        "duration_days": round(end - start, 1) if start is not None and end is not None else None,
    }


def compute_transit_channels(
    personality: list[dict],
    design: list[dict],
    transit_planets: list[dict],
    jd_ut: float | None = None,
) -> list[dict]:
    """Channels a transiting body completes with a gate of the birth chart.

    `transit_planets` are tropical positions (`name`, `longitude`), as
    `compute_all_planets` returns them; the Earth and the South Node are
    derived from the Sun and the true node. Channels the chart already has
    are skipped. With `jd_ut` (the moment of the positions) every entry also
    says when the body entered its gate and when it leaves it.

    Until 1.0.4 the report checked this only for the Sun and the Moon, and
    the model then told a reader "you do not have Gate 26" while a transit
    was closing the 26-44 channel on that very gate (2026-11-02).
    """
    natal_gates: dict[int, list[str]] = {}
    for label, activations in (("Personality", personality), ("Design", design)):
        for activation in activations:
            natal_gates.setdefault(int(activation["gate"]), []).append(
                f"{activation['name']} ({label})"
            )
    mechanics = compute_hd_mechanics(personality, design)
    defined_centers = set(mechanics["defined_centers"])
    natal_channels = {tuple(channel["gates"]) for channel in mechanics["channels"]}

    by_name = {planet["name"]: planet for planet in transit_planets}
    bodies = [(planet["name"], float(planet["longitude"])) for planet in transit_planets]
    for derived, source in _OPPOSITE_BODIES.items():
        if source in by_name:
            bodies.append((derived, (float(by_name[source]["longitude"]) + 180.0) % 360.0))

    found: list[dict] = []
    for name, longitude in bodies:
        activation = longitude_to_gate_line(longitude)
        gate = activation["gate"]
        for gate_a, gate_b in HD_CHANNELS:
            if gate not in (gate_a, gate_b) or (gate_a, gate_b) in natal_channels:
                continue
            partner = gate_b if gate == gate_a else gate_a
            if partner not in natal_gates:
                continue
            centers = [HD_GATE_TO_CENTER[gate_a], HD_GATE_TO_CENTER[gate_b]]
            entry = {
                "transit_body": name,
                "transit_gate": gate,
                "transit_line": activation["line"],
                "natal_gate": partner,
                "natal_bodies": natal_gates[partner],
                "channel": f"{gate_a}-{gate_b}",
                "centers": centers,
                "newly_defined_centers": [c for c in dict.fromkeys(centers) if c not in defined_centers],
            }
            if jd_ut is not None and name in _GATE_SCAN:
                entry.update(transit_gate_window(name, jd_ut))
            found.append(entry)
    return found


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
