"""Vimshottari Dasha calculation (D5).

Derives the 120-year Vimshottari planetary-period timeline from the natal
Moon's sidereal longitude (its Nakshatra). Produces the birth-Mahadasha
balance, the full Mahadasha sequence with Antardashas, and the period active
on a chosen reference date (used to feed Module 9 — the Life Timeline).
"""

from datetime import date, datetime, timedelta
from typing import Final

from eldermind_core.core.config import NAKSHATRA_DEGREES

# Vimshottari sequence of lords and their period lengths in years (sum = 120).
VIMSHOTTARI_ORDER: Final[list[str]] = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
]
VIMSHOTTARI_YEARS: Final[dict[str, float]] = {
    "Ketu": 7.0,
    "Venus": 20.0,
    "Sun": 6.0,
    "Moon": 10.0,
    "Mars": 7.0,
    "Rahu": 18.0,
    "Jupiter": 16.0,
    "Saturn": 19.0,
    "Mercury": 17.0,
}
VIMSHOTTARI_TOTAL_YEARS: Final[float] = 120.0

# Sidereal solar year length used to convert Dasha years into calendar days.
DAYS_PER_YEAR: Final[float] = 365.25

# Nakshatra names indexed 0..26 (mirrors eldermind_core.core.config.NAKSHATRA_NAMES order).
from eldermind_core.core.config import NAKSHATRA_NAMES  # noqa: E402

# Avakahada Chakra mappings derived from the natal Moon's Nakshatra.
NAKSHATRA_GANA: Final[dict[str, str]] = {
    "Ashwini": "Deva",
    "Bharani": "Manushya",
    "Krittika": "Rakshasa",
    "Rohini": "Manushya",
    "Mrigashira": "Deva",
    "Ardra": "Manushya",
    "Punarvasu": "Deva",
    "Pushya": "Deva",
    "Ashlesha": "Rakshasa",
    "Magha": "Rakshasa",
    "Purva Phalguni": "Manushya",
    "Uttara Phalguni": "Manushya",
    "Hasta": "Deva",
    "Chitra": "Rakshasa",
    "Swati": "Deva",
    "Vishakha": "Rakshasa",
    "Anuradha": "Deva",
    "Jyeshtha": "Rakshasa",
    "Mula": "Rakshasa",
    "Purva Ashadha": "Manushya",
    "Uttara Ashadha": "Manushya",
    "Shravana": "Deva",
    "Dhanishta": "Rakshasa",
    "Shatabhisha": "Rakshasa",
    "Purva Bhadrapada": "Manushya",
    "Uttara Bhadrapada": "Manushya",
    "Revati": "Deva",
}

NAKSHATRA_YONI: Final[dict[str, str]] = {
    "Ashwini": "Koń",
    "Bharani": "Słoń",
    "Krittika": "Owca",
    "Rohini": "Wąż",
    "Mrigashira": "Wąż",
    "Ardra": "Pies",
    "Punarvasu": "Kot",
    "Pushya": "Owca",
    "Ashlesha": "Kot",
    "Magha": "Szczur",
    "Purva Phalguni": "Szczur",
    "Uttara Phalguni": "Krowa",
    "Hasta": "Bawół",
    "Chitra": "Tygrys",
    "Swati": "Bawół",
    "Vishakha": "Tygrys",
    "Anuradha": "Jeleń",
    "Jyeshtha": "Jeleń",
    "Mula": "Pies",
    "Purva Ashadha": "Małpa",
    "Uttara Ashadha": "Nakula",
    "Shravana": "Małpa",
    "Dhanishta": "Lew",
    "Shatabhisha": "Koń",
    "Purva Bhadrapada": "Lew",
    "Uttara Bhadrapada": "Krowa",
    "Revati": "Słoń",
}

NAKSHATRA_NADI: Final[dict[str, str]] = {
    "Ashwini": "Vata",
    "Bharani": "Pitta",
    "Krittika": "Kapha",
    "Rohini": "Kapha",
    "Mrigashira": "Pitta",
    "Ardra": "Vata",
    "Punarvasu": "Vata",
    "Pushya": "Pitta",
    "Ashlesha": "Kapha",
    "Magha": "Kapha",
    "Purva Phalguni": "Pitta",
    "Uttara Phalguni": "Vata",
    "Hasta": "Vata",
    "Chitra": "Pitta",
    "Swati": "Kapha",
    "Vishakha": "Kapha",
    "Anuradha": "Pitta",
    "Jyeshtha": "Vata",
    "Mula": "Vata",
    "Purva Ashadha": "Pitta",
    "Uttara Ashadha": "Kapha",
    "Shravana": "Kapha",
    "Dhanishta": "Pitta",
    "Shatabhisha": "Vata",
    "Purva Bhadrapada": "Pitta",
    "Uttara Bhadrapada": "Kapha",
    "Revati": "Kapha",
}

NAKSHATRA_VARNA: Final[dict[str, str]] = {
    "Ashwini": "Brahmin",
    "Bharani": "Kshatriya",
    "Krittika": "Vaishya",
    "Rohini": "Shudra",
    "Mrigashira": "Shudra",
    "Ardra": "Shudra",
    "Punarvasu": "Vaishya",
    "Pushya": "Brahmin",
    "Ashlesha": "Shudra",
    "Magha": "Kshatriya",
    "Purva Phalguni": "Kshatriya",
    "Uttara Phalguni": "Vaishya",
    "Hasta": "Brahmin",
    "Chitra": "Vaishya",
    "Swati": "Shudra",
    "Vishakha": "Vaishya",
    "Anuradha": "Brahmin",
    "Jyeshtha": "Shudra",
    "Mula": "Kshatriya",
    "Purva Ashadha": "Kshatriya",
    "Uttara Ashadha": "Shudra",
    "Shravana": "Shudra",
    "Dhanishta": "Shudra",
    "Shatabhisha": "Brahmin",
    "Purva Bhadrapada": "Brahmin",
    "Uttara Bhadrapada": "Kshatriya",
    "Revati": "Vaishya",
}


def compute_avakahada_chakra(nakshatra_name: str) -> dict:
    """Return the Avakahada Chakra attributes for a given Nakshatra.

    The Avakahada Chakra is a compact Vedic fingerprint of the natal Moon's
    lunar mansion. It is used by Module 5 (Jyotish) to ground the reading in
    concrete, traditional attributes rather than letting the model guess them.
    """
    if nakshatra_name not in NAKSHATRA_NAMES:
        raise ValueError(f"Unknown Nakshatra: {nakshatra_name!r}")

    return {
        "nakshatra": nakshatra_name,
        "gana": NAKSHATRA_GANA[nakshatra_name],
        "yoni": NAKSHATRA_YONI[nakshatra_name],
        "nadi": NAKSHATRA_NADI[nakshatra_name],
        "varna": NAKSHATRA_VARNA[nakshatra_name],
    }


def _years_to_delta(years: float) -> timedelta:
    """Convert a Dasha duration in years into a calendar timedelta."""
    return timedelta(days=years * DAYS_PER_YEAR)


def _order_from(lord: str) -> list[str]:
    """Return the Vimshottari lord order cycled to start at ``lord``."""
    start = VIMSHOTTARI_ORDER.index(lord)
    return [VIMSHOTTARI_ORDER[(start + i) % 9] for i in range(9)]


def _build_antardashas(
    maha_lord: str, maha_start: date, maha_years: float
) -> list[dict]:
    """Build the Antardasha (sub-period) sequence within a Mahadasha.

    Each Antardasha is proportional: its length equals the Mahadasha length
    scaled by the sub-lord's share of the 120-year cycle.

    Args:
        maha_lord: Ruling planet of the Mahadasha.
        maha_start: Start date of the (full) Mahadasha.
        maha_years: Full length of the Mahadasha in years.

    Returns:
        List of Antardasha dictionaries with lord, start and end dates.
    """
    antardashas: list[dict] = []
    cursor = maha_start
    for sub_lord in _order_from(maha_lord):
        sub_years = maha_years * (VIMSHOTTARI_YEARS[sub_lord] / VIMSHOTTARI_TOTAL_YEARS)
        sub_end = cursor + _years_to_delta(sub_years)
        antardashas.append({"lord": sub_lord, "start": cursor, "end": sub_end})
        cursor = sub_end
    return antardashas


def compute_vimshottari_dasha(
    moon_sidereal_longitude: float,
    birth_dt: datetime,
    reference_date: date | None = None,
    *,
    lifespan_years: float = 100.0,
) -> dict:
    """Compute the Vimshottari Dasha timeline from the natal Moon.

    Args:
        moon_sidereal_longitude: Sidereal (Lahiri) longitude of the Moon in degrees.
        birth_dt: Birth moment (used only for its calendar date).
        reference_date: Date at which to report the active period. Defaults to today.
        lifespan_years: How far ahead to project the Mahadasha sequence.

    Returns:
        Dictionary matching the ``VimshottariDasha`` schema.
    """
    if reference_date is None:
        reference_date = date.today()

    birth_date = birth_dt.date()
    normalized = moon_sidereal_longitude % 360.0

    nak_index = int(normalized // NAKSHATRA_DEGREES) % 27
    nak_start = nak_index * NAKSHATRA_DEGREES
    fraction_elapsed = (normalized - nak_start) / NAKSHATRA_DEGREES

    moon_nakshatra = NAKSHATRA_NAMES[nak_index]
    birth_lord = VIMSHOTTARI_ORDER[nak_index % 9]
    birth_lord_full_years = VIMSHOTTARI_YEARS[birth_lord]
    balance_years = (1.0 - fraction_elapsed) * birth_lord_full_years

    # Virtual start of the birth Mahadasha (before birth), so Antardashas align.
    elapsed_years = fraction_elapsed * birth_lord_full_years
    virtual_maha_start = birth_date - _years_to_delta(elapsed_years)

    # Build the Mahadasha sequence from the birth lord until the lifespan is covered.
    mahadashas: list[dict] = []
    cursor = virtual_maha_start
    lord_cycle = _order_from(birth_lord)
    horizon = birth_date + _years_to_delta(lifespan_years)
    i = 0
    while cursor < horizon:
        lord = lord_cycle[i % 9]
        maha_years = VIMSHOTTARI_YEARS[lord]
        maha_end = cursor + _years_to_delta(maha_years)
        mahadashas.append(
            {
                "lord": lord,
                "start": cursor,
                "end": maha_end,
                "antardashas": _build_antardashas(lord, cursor, maha_years),
            }
        )
        cursor = maha_end
        i += 1

    # Timeline for output: clip the first Mahadasha to the birth date and drop
    # Antardashas that ended before birth (they belong to previous incarnation cycle).
    timeline: list[dict] = []
    for index, maha in enumerate(mahadashas):
        entry = {
            "lord": maha["lord"],
            "start": max(maha["start"], birth_date) if index == 0 else maha["start"],
            "end": maha["end"],
            "antardashas": [
                a for a in maha["antardashas"]
                if index != 0 or a["end"] > birth_date
            ],
        }
        timeline.append(entry)

    # Active period on the reference date.
    current = _find_current(mahadashas, reference_date)

    return {
        "moon_nakshatra": moon_nakshatra,
        "moon_nakshatra_lord": birth_lord,
        "balance_at_birth": {
            "lord": birth_lord,
            "years_remaining": round(balance_years, 4),
        },
        "current": current,
        "timeline": timeline,
    }


def _find_current(mahadashas: list[dict], reference_date: date) -> dict:
    """Return the Mahadasha (with only its active Antardasha) at a given date."""
    for maha in mahadashas:
        if maha["start"] <= reference_date < maha["end"]:
            active_antar = [
                a for a in maha["antardashas"]
                if a["start"] <= reference_date < a["end"]
            ]
            return {
                "lord": maha["lord"],
                "start": maha["start"],
                "end": maha["end"],
                "antardashas": active_antar,
            }
    # Reference date beyond the projected horizon: return the last Mahadasha.
    last = mahadashas[-1]
    return {
        "lord": last["lord"],
        "start": last["start"],
        "end": last["end"],
        "antardashas": [],
    }
