"""Application configuration and constants for the Eldermind astrological engine."""

from typing import Final

# Default house system: Placidus for Western astrology.
HOUSE_SYSTEM_WESTERN: Final[bytes] = b"P"

# House system: Whole Sign for Vedic astrology.
HOUSE_SYSTEM_VEDIC: Final[bytes] = b"W"

# Number of zodiac signs and degrees per sign.
SIGNS_COUNT: Final[int] = 12
DEGREES_PER_SIGN: Final[float] = 30.0

# Zodiac sign names in order starting at 0 degrees Aries.
ZODIAC_SIGNS: Final[list[str]] = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

# Planet identifier mapping for pyswisseph.
PLANET_IDS: Final[dict[str, int]] = {
    "Sun": 0,
    "Moon": 1,
    "Mercury": 2,
    "Venus": 3,
    "Mars": 4,
    "Jupiter": 5,
    "Saturn": 6,
    "Uranus": 7,
    "Neptune": 8,
    "Pluto": 9,
    "TrueNode": 11,
}

# Ptolemaic aspects used in Western astrology. The orb is set globally
# to 8 degrees for Phase 2 and can be made planet-specific later.
ASPECT_DEFINITIONS: Final[list[dict]] = [
    {"name": "Conjunction", "angle": 0.0},
    {"name": "Sextile", "angle": 60.0},
    {"name": "Square", "angle": 90.0},
    {"name": "Trine", "angle": 120.0},
    {"name": "Opposition", "angle": 180.0},
]
DEFAULT_ORB_DEGREES: Final[float] = 8.0

# Nakshatra (lunar mansion) configuration for Jyotish.
NAKSHATRA_COUNT: Final[int] = 27
NAKSHATRA_DEGREES: Final[float] = 360.0 / NAKSHATRA_COUNT  # 13.3333...
PADA_COUNT: Final[int] = 4
PADA_DEGREES: Final[float] = NAKSHATRA_DEGREES / PADA_COUNT  # 3.3333...
NAKSHATRA_NAMES: Final[list[str]] = [
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
]

# Bodies for which Nakshatra/Pada are calculated in the Vedic section.
NAKSHATRA_BODIES: Final[set[str]] = {"Sun", "Moon", "Ascendant"}
