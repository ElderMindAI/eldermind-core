"""Human Design constants: gate/line mapping and body list."""

from typing import Final

# Human Design circle starts at 02°00'00" Aquarius = 302.0°.
HD_GATE_START_DEGREES: Final[float] = 302.0

# Gate angular size: 5°37'30" = 5.625° exactly.
HD_GATE_DEGREES: Final[float] = 5.625

# Line angular size: 0°56'15" = 0.9375° exactly.
HD_LINE_DEGREES: Final[float] = 0.9375

# Number of gates and lines per gate.
HD_GATE_COUNT: Final[int] = 64
HD_LINE_COUNT: Final[int] = 6

# Canonical Rave Mandala gate order around the zodiac starting from
# HD_GATE_START_DEGREES. This sequence is taken from the authoritative
# interactive Rave Mandala wheel (ascendantgate.com) and begins with gate 41
# at 02° Aquarius (302°), proceeding counter-clockwise through the zodiac.
HD_GATE_SEQUENCE: Final[list[int]] = [
    41, 19, 13, 49, 30, 55, 37, 63, 22, 36, 25, 17, 21, 51, 42, 3,
    27, 24, 2, 23, 8, 20, 16, 35, 45, 12, 15, 52, 39, 53, 62, 56,
    31, 33, 7, 4, 29, 59, 40, 64, 47, 6, 46, 18, 48, 57, 32, 50,
    28, 44, 1, 43, 14, 34, 9, 5, 26, 11, 10, 58, 38, 54, 61, 60,
]

# Bodies used in Human Design calculations.
HD_BODY_IDS: Final[dict[str, int]] = {
    "Sun": 0,
    "Earth": 0,
    "Moon": 1,
    "NorthNode": 11,
    "SouthNode": 11,
    "Mercury": 2,
    "Venus": 3,
    "Mars": 4,
    "Jupiter": 5,
    "Saturn": 6,
    "Uranus": 7,
    "Neptune": 8,
    "Pluto": 9,
}

# ---------------------------------------------------------------------------
# HUMAN DESIGN MECHANICS (D5): centers, gate->center map, channels, type info.
# The engine derives the *mechanics* deterministically; interpretive meanings
# (gate/channel/center descriptions) live in the RAG knowledge base.
# ---------------------------------------------------------------------------

# The nine Human Design centers in a stable, canonical order (top to bottom).
HD_CENTERS: Final[list[str]] = [
    "Head",
    "Ajna",
    "Throat",
    "G",
    "Heart",
    "SolarPlexus",
    "Sacral",
    "Spleen",
    "Root",
]

# The four motor centers (pressure/energy sources).
HD_MOTOR_CENTERS: Final[frozenset[str]] = frozenset(
    {"Sacral", "Heart", "SolarPlexus", "Root"}
)

# Gate -> Center assignment for all 64 gates (3+6+11+8+4+9+7+7+9 = 64).
HD_GATE_TO_CENTER: Final[dict[int, str]] = {
    # Head (3)
    64: "Head", 61: "Head", 63: "Head",
    # Ajna (6)
    47: "Ajna", 24: "Ajna", 4: "Ajna", 11: "Ajna", 43: "Ajna", 17: "Ajna",
    # Throat (11)
    62: "Throat", 23: "Throat", 56: "Throat", 35: "Throat", 12: "Throat",
    45: "Throat", 33: "Throat", 8: "Throat", 31: "Throat", 20: "Throat", 16: "Throat",
    # G / Identity (8)
    7: "G", 1: "G", 13: "G", 10: "G", 25: "G", 46: "G", 2: "G", 15: "G",
    # Heart / Ego / Will (4)
    21: "Heart", 40: "Heart", 26: "Heart", 51: "Heart",
    # Sacral (9)
    34: "Sacral", 5: "Sacral", 14: "Sacral", 29: "Sacral", 59: "Sacral",
    9: "Sacral", 3: "Sacral", 42: "Sacral", 27: "Sacral",
    # Spleen (7)
    48: "Spleen", 57: "Spleen", 44: "Spleen", 50: "Spleen", 32: "Spleen",
    28: "Spleen", 18: "Spleen",
    # Solar Plexus / Emotional (7)
    6: "SolarPlexus", 37: "SolarPlexus", 30: "SolarPlexus", 55: "SolarPlexus",
    49: "SolarPlexus", 22: "SolarPlexus", 36: "SolarPlexus",
    # Root (9)
    58: "Root", 38: "Root", 54: "Root", 53: "Root", 60: "Root",
    52: "Root", 19: "Root", 39: "Root", 41: "Root",
}

# The 36 channels as gate pairs. Connected centers are derived from the
# gate->center map, so only the gate pairs are stored here.
HD_CHANNELS: Final[list[tuple[int, int]]] = [
    (1, 8), (2, 14), (3, 60), (4, 63), (5, 15), (6, 59), (7, 31), (9, 52),
    (10, 20), (10, 34), (10, 57), (11, 56), (12, 22), (13, 33), (16, 48),
    (17, 62), (18, 58), (19, 49), (20, 34), (20, 57), (21, 45), (23, 43),
    (24, 61), (25, 51), (26, 44), (27, 50), (28, 38), (29, 46), (30, 41),
    (32, 54), (34, 57), (35, 36), (37, 40), (39, 55), (42, 53), (47, 64),
]

# Canonical labels per Type: Strategy, Signature (aligned) and Not-Self theme.
# These are fixed HD terminology (not interpretive prose).
HD_TYPE_INFO: Final[dict[str, dict[str, str]]] = {
    "Manifestor": {
        "strategy": "To Inform",
        "signature": "Peace",
        "not_self_theme": "Anger",
    },
    "Generator": {
        "strategy": "To Respond",
        "signature": "Satisfaction",
        "not_self_theme": "Frustration",
    },
    "Manifesting Generator": {
        "strategy": "To Respond, then Inform",
        "signature": "Satisfaction and Peace",
        "not_self_theme": "Frustration and Anger",
    },
    "Projector": {
        "strategy": "Wait for the Invitation",
        "signature": "Success",
        "not_self_theme": "Bitterness",
    },
    "Reflector": {
        "strategy": "Wait a Lunar Cycle",
        "signature": "Surprise",
        "not_self_theme": "Disappointment",
    },
}

# Incarnation Cross angle by profile (conscious/unconscious Sun line pair).
HD_CROSS_ANGLE_BY_PROFILE: Final[dict[str, str]] = {
    "1/3": "Right Angle", "1/4": "Right Angle", "2/4": "Right Angle",
    "2/5": "Right Angle", "3/5": "Right Angle", "3/6": "Right Angle",
    "4/6": "Right Angle",
    "4/1": "Juxtaposition",
    "5/1": "Left Angle", "5/2": "Left Angle", "6/2": "Left Angle",
    "6/3": "Left Angle",
}
