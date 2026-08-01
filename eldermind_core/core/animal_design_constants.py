"""Animal Design ("Mammalian Design System") constants.

Source: Genetic Matrix's public "Animal Design" Learn Hub page
(https://www.geneticmatrix.com/learn-hub/animals/index.html) — a simplified,
15-gate Human Design variant for mammals: 5 centers (no Head, Ajna, Heart or
Solar Plexus), organized into 3 groups of 5 gates each, each group anchored
by a "Cross-Species Portal Gate" that bridges to a human-only gate.

Deliberately kept fully separate from `eldermind_core.core.hd_constants` (the human HD
knowledge base/engine must not be mixed with the animal one), even though the
gate numbers and underlying 64-gate wheel geometry are shared and reused via
`eldermind_core.services.human_design.longitude_to_gate_line`.
"""

from typing import Final

# The 15 gates that make up the Mammalian Design System matrix. Any
# Personality/Design activation whose gate falls outside this set is
# discarded entirely — "only activations that fall within the 15 mammalian
# gates matter" (Genetic Matrix).
ANIMAL_GATES: Final[frozenset[int]] = frozenset(
    {19, 28, 38, 42, 53, 12, 27, 50, 5, 15, 62, 20, 57, 8, 1}
)

# The 5 centers used in the animal system (a strict subset of the 9 human
# HD centers — no Head, Ajna, Heart or Solar Plexus).
ANIMAL_CENTERS: Final[list[str]] = ["Root", "Sacral", "Spleen", "Throat", "G"]

# Gate -> Center, restricted to the 15 mammalian gates. Values match the
# human HD_GATE_TO_CENTER mapping exactly (same wheel), just filtered down.
ANIMAL_GATE_TO_CENTER: Final[dict[int, str]] = {
    # Root (3)
    19: "Root", 38: "Root", 53: "Root",
    # Sacral (3)
    42: "Sacral", 27: "Sacral", 5: "Sacral",
    # Spleen (3)
    28: "Spleen", 50: "Spleen", 57: "Spleen",
    # Throat (4)
    12: "Throat", 62: "Throat", 20: "Throat", 8: "Throat",
    # G (2)
    15: "G", 1: "G",
}

# Only Root and Sacral exist as "motor" centers in the animal system (no
# Heart/Solar Plexus at all).
ANIMAL_MOTOR_CENTERS: Final[frozenset[str]] = frozenset({"Root", "Sacral"})

# The 6 channels whose *both* gates fall within the 15-gate matrix (verified
# against the full 36-channel human HD_CHANNELS list). The other 3 "channels"
# involving these gates (19-49, 12-22, 62-17) are Cross-Species Portals —
# the human-side gate isn't part of the animal matrix, so they never form an
# internal animal channel; see ANIMAL_CROSS_SPECIES_PORTALS below.
ANIMAL_CHANNELS: Final[list[tuple[int, int]]] = [
    (1, 8),
    (5, 15),
    (20, 57),
    (27, 50),
    (28, 38),
    (42, 53),
]

# The 3 groups of 5 gates, each anchored by a Cross-Species Portal Gate.
ANIMAL_GROUPS: Final[dict[str, dict]] = {
    "Territory": {
        "portal_gate": 19,
        "gates": [19, 28, 38, 42, 53],
        "centers": ["Root", "Spleen", "Sacral"],
    },
    "Metamorphosis": {
        "portal_gate": 12,
        "gates": [12, 27, 50, 5, 15],
        "centers": ["Throat", "Sacral", "Spleen", "G"],
    },
    "Alpha": {
        "portal_gate": 62,
        "gates": [62, 20, 57, 8, 1],
        "centers": ["Throat", "Spleen", "G"],
    },
}

# Cross-Species Portal Gates: animal gate -> (human gate, label). Activated
# when the animal's chart has the animal-side gate; the human-side gate is
# meaningless for the animal's own chart, it only matters for a *human's*
# chart when checking compatibility (out of scope for this simplified tool).
ANIMAL_CROSS_SPECIES_PORTALS: Final[dict[int, dict[str, str | int]]] = {
    19: {"human_gate": 49, "label": "Resource"},
    12: {"human_gate": 22, "label": "Friend"},
    62: {"human_gate": 17, "label": "Worker"},
}
