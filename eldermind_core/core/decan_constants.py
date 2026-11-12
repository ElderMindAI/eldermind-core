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

#: Court cards (16). Book T ("Book T - The Tarot", the Golden Dawn text; on the
#: site "Ksiega T") and Crowley's "The Book of Thoth" (1944, Part Three) give the
#: same zodiac spans, compared on 2026-11-12: each Knight, Queen and Prince rules
#: 30 deg, from 20 deg of one sign to 20 deg of the next (Crowley: "from the 21st
#: degree of ... to the 20th degree of ..."). A span is keyed by its start sign.
#: The Princesses rule a quadrant of the heavens around the North Pole, above the
#: fixed ("cherubic") sign of their element; neither source gives them ecliptic
#: degrees (Crowley: "The Princesses have no Zodiacal attribution").
#:
#: Card numbers follow the deck files (Rider-Waite ranks): 11 Page, 12 Knight,
#: 13 Queen, 14 King. The Golden Dawn rider (Knight) is the deck's Knight and the
#: Prince in his chariot is the deck's King, as Book T itself labels them
#: ("Knight of Wands", "King of Wands", "Knave of Wands") and as Crowley's second
#: naming has it ("Knight, Queen, King and Princess"). Owner's decision 12.11.
COURT_SPAN_START_DEGREE: Final[float] = 20.0
COURT_SPAN_DEGREES: Final[float] = 30.0

#: Golden Dawn rank -> (deck card number, elemental part of the suit).
COURT_RANKS: Final[dict[str, tuple[int, str]]] = {
    "knight": (12, "fire"),
    "queen": (13, "water"),
    "prince": (14, "air"),
    "princess": (11, "earth"),
}

#: (suit, Golden Dawn rank, start sign of the span or None, Book T title).
COURT_CARDS: Final[list[tuple[str, str, str | None, str]]] = [
    ("wands", "knight", "Scorpio", "The Lord of the Flame and the Lightning; The King of the Spirits of Fire"),
    ("wands", "queen", "Pisces", "The Queen of the Thrones of Flame"),
    ("wands", "prince", "Cancer", "The Prince of the Chariot of Fire"),
    ("wands", "princess", None, "The Princess of the Shining Flame; The Rose of the Palace of Fire"),
    ("cups", "knight", "Aquarius", "The Lord of the Waves and the Waters; The King of the Hosts of the Sea"),
    ("cups", "queen", "Gemini", "The Queen of the Thrones of the Waters"),
    ("cups", "prince", "Libra", "The Prince of the Chariot of the Waters"),
    ("cups", "princess", None, "The Princess of the Waters; The Lotus of the Palace of the Floods"),
    ("swords", "knight", "Taurus", "The Lord of the Winds and the Breezes; The King of the Spirits of Air"),
    ("swords", "queen", "Virgo", "The Queen of the Thrones of Air"),
    ("swords", "prince", "Capricorn", "The Prince of the Chariot of the Winds"),
    ("swords", "princess", None, "The Princess of the Rushing Winds; The Lotus of the Palace of Air"),
    ("pentacles", "knight", "Leo", "The Lord of the Wide and Fertile Land; The King of the Spirits of Earth"),
    ("pentacles", "queen", "Sagittarius", "The Queen of the Thrones of Earth"),
    ("pentacles", "prince", "Aries", "The Prince of the Chariot of Earth"),
    ("pentacles", "princess", None, "The Princess of the Echoing Hills; The Rose of the Palace of Earth"),
]

#: Fixed sign above which each Princess's quadrant lies (Book T: "above the
#: respective Cherubic Signs of the Zodiac").
PRINCESS_CHERUBIC_SIGN: Final[dict[str, str]] = {
    "wands": "Leo", "cups": "Scorpio", "swords": "Aquarius", "pentacles": "Taurus",
}

#: The 22 trumps, numbered as in the deck files (Rider-Waite and Book T order:
#: 8 Strength / Fortitude, 11 Justice). (number, Book T name, kind, attribution).
#: Book T and Crowley agree on every sign, planet and element; Crowley swaps only
#: the Hebrew letters of the Emperor and the Star and the numbers 8 and 11, which
#: change no attribution. Judgement is "Spirit and Fire" and the Universe "Earth
#: and Saturn" in Book T; the first-named attribution is kept (Fire, Saturn) and
#: the second is in MAJOR_SECOND. Uranus, Neptune and Pluto have no trump in
#: either source (owner's decision 12.11: none is shown).
MAJOR_ARCANA: Final[list[tuple[int, str, str, str]]] = [
    (0, "The Foolish Man", "element", "air"),
    (1, "The Magician", "planet", "Mercury"),
    (2, "The High Priestess", "planet", "Moon"),
    (3, "The Empress", "planet", "Venus"),
    (4, "The Emperor", "sign", "Aries"),
    (5, "The Hierophant", "sign", "Taurus"),
    (6, "The Lovers", "sign", "Gemini"),
    (7, "The Chariot", "sign", "Cancer"),
    (8, "Fortitude", "sign", "Leo"),
    (9, "The Hermit", "sign", "Virgo"),
    (10, "The Wheel", "planet", "Jupiter"),
    (11, "Justice", "sign", "Libra"),
    (12, "The Hanged Man", "element", "water"),
    (13, "Death", "sign", "Scorpio"),
    (14, "Temperance", "sign", "Sagittarius"),
    (15, "The Devil", "sign", "Capricorn"),
    (16, "The Blasted Tower", "planet", "Mars"),
    (17, "The Star", "sign", "Aquarius"),
    (18, "The Moon", "sign", "Pisces"),
    (19, "The Sun", "planet", "Sun"),
    (20, "The Judgment", "element", "fire"),
    (21, "The Universe", "planet", "Saturn"),
]

#: Second attribution printed in Book T for two trumps.
MAJOR_SECOND: Final[dict[int, str]] = {20: "Spirit", 21: "Earth"}

#: Book T titles of the trumps ("The Twenty-Two Keys of the Book").
MAJOR_TITLES_BOOK_T: Final[dict[int, str]] = {
    0: "The Spirit of Aether",  # Book T prints the Greek word, AITHER
    1: "The Magus of Power",
    2: "The Priestess of the Silver Star",
    3: "The Daughter of the Mighty Ones",
    4: "Sun of the Morning, Chief among the Mighty",
    5: "The Magus of the Eternal",
    6: "The Children of the Voice; the Oracles of the Mighty Gods",
    7: "The Child of the Powers of the Waters; the Lord of the Triumph of Light",
    8: "The Daughter of the Flaming Sword",
    9: "The Magus of the Voice of Power, the Prophet of the Eternal",
    10: "The Lord of the Forces of Life",
    11: "The Daughter of the Lords of Truth; the Ruler of the Balance",
    12: "The Spirit of the Mighty Waters",
    13: "The Child of the Great Transformers; the Lord of the Gates of Death",
    14: "The Daughter of the Reconcilers; the Bringer-Forth of Life",
    15: "The Lord of the Gates of Matter; the Child of the Forces of Time",
    16: "The Lord of the Hosts of the Mighty",
    17: "The Daughter of the Firmament; the Dweller between the Waters",
    18: "The Ruler of Flux and Reflux; the Child of the Sons of the Mighty",
    19: "The Lord of the Fire of the World",
    20: "The Spirit of the Primal Fire",
    21: "The Great One of the Night of Time",
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
