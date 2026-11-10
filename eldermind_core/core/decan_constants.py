"""Decans and their Golden Dawn tarot cards: the 36 small cards numbered 2 to 10.

Source of the table: the Golden Dawn text "Book T - The Tarot" (published in full
by Israel Regardie), table "Lord of / Decan / In" for cards 21-56. Every row of
`DECANS` below was compared with that table (card, title, planet, sign) on
2026-11-10; all 36 agree. The tests also re-derive each row from the rules the
table follows (element -> suit, modality -> number, Chaldean order -> ruler), so
a typo here fails twice.

Two notes from the source that matter to a careful reader:

* Book T numbers the decans from the royal star Cor Leonis (Regulus), so its
  list starts with the 5 of Wands in Leo. Modern decks and practice (Thoth,
  Wang, every published decan calculator) apply the table to the tropical
  zodiac from 0 deg Aries, and so does this module.
* Book T itself has two slips outside the main table: "Abundant Success" for
  the 8 of Cups and "9 of Swords" for Pisces in the per-planet lists. The main
  table (used here) says "Abandoned Success" and the 9 of Cups.

The engine stays language-neutral: suit keys and English titles here, display
names (Polish: Bulawy, Kielichy, Miecze, Pentakle) live in the consumers.
"""

from typing import Final

#: Size of one decan in degrees of ecliptic longitude.
DECAN_DEGREES: Final[float] = 10.0
DECAN_COUNT: Final[int] = 36
DECANS_PER_SIGN: Final[int] = 3

#: Suit key by element. Golden Dawn: Wands fire, Cups water, Swords air,
#: Pentacles earth.
SUIT_BY_ELEMENT: Final[dict[str, str]] = {
    "fire": "wands",
    "water": "cups",
    "air": "swords",
    "earth": "pentacles",
}

#: Element of each sign, in zodiac order from Aries.
SIGN_ELEMENTS: Final[list[str]] = [
    "fire", "earth", "air", "water",
    "fire", "earth", "air", "water",
    "fire", "earth", "air", "water",
]

#: First card number of a sign by modality: cardinal 2-3-4, fixed 5-6-7,
#: mutable 8-9-10.
FIRST_NUMBER_BY_MODALITY: Final[dict[str, int]] = {
    "cardinal": 2,
    "fixed": 5,
    "mutable": 8,
}

SIGN_MODALITIES: Final[list[str]] = ["cardinal", "fixed", "mutable"] * 4

#: Chaldean order as it runs through the decans, starting with Mars in the first
#: decan of Aries (Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon, rotated).
#: 36 = 5 * 7 + 1, so the last decan of Pisces is Mars again.
CHALDEAN_DECAN_ORDER: Final[list[str]] = [
    "Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter",
]

#: Traditional sign rulers (no outer planets), used by the triplicity school.
TRADITIONAL_SIGN_RULERS: Final[dict[str, str]] = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

#: Modern Western rulers: Pluto, Uranus and Neptune for Scorpio, Aquarius and
#: Pisces. Offered because much of 20th-century Western practice uses them for
#: triplicity decans; which one the product shows is a product decision.
MODERN_SIGN_RULERS: Final[dict[str, str]] = {
    **TRADITIONAL_SIGN_RULERS,
    "Scorpio": "Pluto",
    "Aquarius": "Uranus",
    "Pisces": "Neptune",
}

#: The 36 decans from 0 deg Aries, as in the Book T table:
#: (sign, suit, number, Chaldean ruler, Book T title "Lord of ...").
DECANS: Final[list[tuple[str, str, int, str, str]]] = [
    ("Aries", "wands", 2, "Mars", "Dominion"),
    ("Aries", "wands", 3, "Sun", "Established Strength"),
    ("Aries", "wands", 4, "Venus", "Perfected Work"),
    ("Taurus", "pentacles", 5, "Mercury", "Material Trouble"),
    ("Taurus", "pentacles", 6, "Moon", "Material Success"),
    ("Taurus", "pentacles", 7, "Saturn", "Success Unfulfilled"),
    ("Gemini", "swords", 8, "Jupiter", "Shortened Force"),
    ("Gemini", "swords", 9, "Mars", "Despair and Cruelty"),
    ("Gemini", "swords", 10, "Sun", "Ruin"),
    ("Cancer", "cups", 2, "Venus", "Love"),
    ("Cancer", "cups", 3, "Mercury", "Abundance"),
    ("Cancer", "cups", 4, "Moon", "Blended Pleasure"),
    ("Leo", "wands", 5, "Saturn", "Strife"),
    ("Leo", "wands", 6, "Jupiter", "Victory"),
    ("Leo", "wands", 7, "Mars", "Valour"),
    ("Virgo", "pentacles", 8, "Sun", "Prudence"),
    ("Virgo", "pentacles", 9, "Venus", "Material Gain"),
    ("Virgo", "pentacles", 10, "Mercury", "Wealth"),
    ("Libra", "swords", 2, "Moon", "Peace Restored"),
    ("Libra", "swords", 3, "Saturn", "Sorrow"),
    ("Libra", "swords", 4, "Jupiter", "Rest from Strife"),
    ("Scorpio", "cups", 5, "Mars", "Loss in Pleasure"),
    ("Scorpio", "cups", 6, "Sun", "Pleasure"),
    ("Scorpio", "cups", 7, "Venus", "Illusionary Success"),
    ("Sagittarius", "wands", 8, "Mercury", "Swiftness"),
    ("Sagittarius", "wands", 9, "Moon", "Great Strength"),
    ("Sagittarius", "wands", 10, "Saturn", "Oppression"),
    ("Capricorn", "pentacles", 2, "Jupiter", "Harmonious Change"),
    ("Capricorn", "pentacles", 3, "Mars", "Material Works"),
    ("Capricorn", "pentacles", 4, "Sun", "Earthly Power"),
    ("Aquarius", "swords", 5, "Venus", "Defeat"),
    ("Aquarius", "swords", 6, "Mercury", "Earned Success"),
    ("Aquarius", "swords", 7, "Moon", "Unstable Effort"),
    ("Pisces", "cups", 8, "Saturn", "Abandoned Success"),
    ("Pisces", "cups", 9, "Jupiter", "Material Happiness"),
    ("Pisces", "cups", 10, "Mars", "Perfected Success"),
]
