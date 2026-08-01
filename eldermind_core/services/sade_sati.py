"""Sade-Sati calculation for Vedic astrology.

Sade-Sati is the 7.5-year period during which Saturn transits the twelfth,
first and second signs from the natal Moon sign. It is divided into three
phases of roughly 2.5 years each:

* Rising    – Saturn in the 12th sign from the Moon
* Peak      – Saturn in the same sign as the Moon
* Setting   – Saturn in the 2nd sign from the Moon

All calculations use the Lahiri (Chitra Paksha) ayanamsa.
"""

from datetime import date, datetime, timedelta
from typing import Final

import swisseph as swe

from eldermind_core.core.config import PLANET_IDS, ZODIAC_SIGNS

# Saturn spends roughly 2.5 years in each sign.
SATURN_DAYS_PER_SIGN: Final[float] = 365.25 * 2.5

# Bracket step used when searching for sign ingresses.
_SEARCH_STEP_DAYS: Final[float] = 5.0

# Search horizon in years when looking backward/forward for a Sade-Sati window.
_SEARCH_HORIZON_YEARS: Final[float] = 20.0

_PHASE_ORDER: Final[list[str]] = ["rising", "peak", "setting"]


def _apply_lahiri_ayanamsa() -> None:
    """Ensure Swiss Ephemeris is in Lahiri sidereal mode."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)


def _saturn_sidereal_longitude(jd_ut: float) -> float:
    """Return Saturn's sidereal (Lahiri) longitude for a given Julian Day."""
    _apply_lahiri_ayanamsa()
    result, err = swe.calc_ut(jd_ut, PLANET_IDS["Saturn"], swe.FLG_SIDEREAL)
    if err and not result:
        raise RuntimeError(f"Saturn calculation failed: {err}")
    return float(result[0]) % 360.0


def _saturn_sign(jd_ut: float) -> int:
    """Return Saturn's sidereal sign index (0=Aries, ..., 11=Pisces)."""
    return int(_saturn_sidereal_longitude(jd_ut) // 30.0) % 12


def _jd_to_date(jd_ut: float) -> date:
    """Convert a Julian Day (UT) to a calendar date.

    Only the calendar date is returned; sub-day precision is dropped because
    Sade-Sati boundaries are reported as dates.
    """
    parts = swe.revjul(jd_ut)
    # swe.revjul returns (year, month, day, hour, ...)
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _date_to_jd(d: date) -> float:
    """Convert a calendar date to Julian Day at 00:00 UT."""
    return swe.julday(d.year, d.month, d.day, 0.0)


def _sign_index(sign_name: str) -> int:
    """Convert a zodiac sign name to its 0-based index."""
    try:
        return ZODIAC_SIGNS.index(sign_name)
    except ValueError as exc:
        raise ValueError(f"Unknown zodiac sign: {sign_name!r}") from exc


def _refine_ingress(
    target_sign: int,
    jd_before: float,
    jd_after: float,
) -> float:
    """Refine a sign-boundary crossing to within a fraction of a day.

    Assumes Saturn crossed from ``target_sign - 1`` (or any other sign) into
    ``target_sign`` somewhere between ``jd_before`` and ``jd_after``.
    """
    lo, hi = jd_before, jd_after
    for _ in range(60):
        mid = (lo + hi) / 2.0
        mid_sign = _saturn_sign(mid)
        if mid_sign == target_sign:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-6:
            break
    return (lo + hi) / 2.0


def _find_ingress(
    source_sign: int,
    target_sign: int,
    start_jd: float,
    *,
    forward: bool,
    horizon_years: float = _SEARCH_HORIZON_YEARS,
) -> float | None:
    """Find an ingress from ``source_sign`` into ``target_sign``.

    When ``forward`` is True the search moves forward in time starting at
    ``start_jd`` and returns the first crossing where Saturn moves from
    ``source_sign`` into ``target_sign``.

    When ``forward`` is False the search moves backward in time and returns
    the most recent such crossing before ``start_jd``.
    """
    step = _SEARCH_STEP_DAYS if forward else -_SEARCH_STEP_DAYS
    limit = start_jd + (horizon_years * 365.25 if forward else -horizon_years * 365.25)

    jd = start_jd
    prev_sign = _saturn_sign(jd)
    while (forward and jd <= limit) or (not forward and jd >= limit):
        curr_sign = _saturn_sign(jd)
        if forward:
            crossing = prev_sign == source_sign and curr_sign == target_sign
        else:
            # Moving backward in time: prev is later, curr is earlier.
            crossing = prev_sign == target_sign and curr_sign == source_sign
        if crossing:
            # The crossing happened between the previous step and the current one.
            if forward:
                return _refine_ingress(target_sign, jd - _SEARCH_STEP_DAYS, jd)
            return _refine_ingress(target_sign, jd, jd + _SEARCH_STEP_DAYS)
        prev_sign = curr_sign
        jd += step
    return None


def compute_sade_sati(
    moon_sign: str,
    reference_date: date | None = None,
) -> dict:
    """Compute the Sade-Sati status for a given natal Moon sign.

    Args:
        moon_sign: Sidereal zodiac sign occupied by the natal Moon.
        reference_date: Date used to determine whether Sade-Sati is active.
            Defaults to today.

    Returns:
        Dictionary with status, phase, phase dates and a breakdown of the
        three Sade-Sati phases. Dates are ISO strings for JSON compatibility.
    """
    if reference_date is None:
        reference_date = date.today()

    moon_index = _sign_index(moon_sign)
    sign_12 = (moon_index - 1) % 12
    sign_1 = moon_index
    sign_2 = (moon_index + 1) % 12
    sign_3 = (moon_index + 2) % 12

    ref_jd = _date_to_jd(reference_date)
    current_saturn_sign = _saturn_sign(ref_jd)

    phase_signs = [sign_12, sign_1, sign_2]
    sade_sati_active = current_saturn_sign in phase_signs

    if sade_sati_active:
        phase_index = phase_signs.index(current_saturn_sign)
        current_phase_name = _PHASE_ORDER[phase_index]

        if phase_index == 0:  # rising
            rising_start_jd = _find_ingress(
                (sign_12 - 1) % 12, sign_12, ref_jd, forward=False
            )
            peak_start_jd = (
                _find_ingress(sign_12, sign_1, rising_start_jd, forward=True)
                if rising_start_jd
                else None
            )
            setting_start_jd = (
                _find_ingress(sign_1, sign_2, peak_start_jd, forward=True)
                if peak_start_jd
                else None
            )
        elif phase_index == 1:  # peak
            peak_start_jd = _find_ingress(sign_12, sign_1, ref_jd, forward=False)
            rising_start_jd = (
                _find_ingress((sign_12 - 1) % 12, sign_12, peak_start_jd, forward=False)
                if peak_start_jd
                else None
            )
            setting_start_jd = (
                _find_ingress(sign_1, sign_2, peak_start_jd, forward=True)
                if peak_start_jd
                else None
            )
        else:  # setting
            setting_start_jd = _find_ingress(sign_1, sign_2, ref_jd, forward=False)
            peak_start_jd = (
                _find_ingress(sign_12, sign_1, setting_start_jd, forward=False)
                if setting_start_jd
                else None
            )
            rising_start_jd = (
                _find_ingress((sign_12 - 1) % 12, sign_12, peak_start_jd, forward=False)
                if peak_start_jd
                else None
            )
    else:
        phase_index = None
        current_phase_name = None
        rising_start_jd = _find_ingress(
            (sign_12 - 1) % 12, sign_12, ref_jd, forward=True
        )
        peak_start_jd = (
            _find_ingress(sign_12, sign_1, rising_start_jd, forward=True)
            if rising_start_jd
            else None
        )
        setting_start_jd = (
            _find_ingress(sign_1, sign_2, peak_start_jd, forward=True)
            if peak_start_jd
            else None
        )

    if rising_start_jd is None or peak_start_jd is None or setting_start_jd is None:
        raise RuntimeError(
            f"Unable to locate a Sade-Sati window for Moon sign {moon_sign!r}"
        )

    sade_end_jd = _find_ingress(sign_2, sign_3, setting_start_jd, forward=True)

    if sade_end_jd is None:
        raise RuntimeError(
            f"Unable to compute complete Sade-Sati timeline for Moon sign {moon_sign!r}"
        )

    phases = [
        {
            "phase": "rising",
            "sign": ZODIAC_SIGNS[sign_12],
            "start": _jd_to_date(rising_start_jd).isoformat(),
            "end": _jd_to_date(peak_start_jd).isoformat(),
        },
        {
            "phase": "peak",
            "sign": ZODIAC_SIGNS[sign_1],
            "start": _jd_to_date(peak_start_jd).isoformat(),
            "end": _jd_to_date(setting_start_jd).isoformat(),
        },
        {
            "phase": "setting",
            "sign": ZODIAC_SIGNS[sign_2],
            "start": _jd_to_date(setting_start_jd).isoformat(),
            "end": _jd_to_date(sade_end_jd).isoformat(),
        },
    ]

    phase_start_date = None
    phase_end_date = None
    if sade_sati_active and phase_index is not None:
        phase_start_date = phases[phase_index]["start"]
        phase_end_date = phases[phase_index]["end"]

    return {
        "status": "active" if sade_sati_active else "inactive",
        "phase": current_phase_name,
        "moon_sign": moon_sign,
        "saturn_sign": ZODIAC_SIGNS[current_saturn_sign],
        "start_date": _jd_to_date(rising_start_jd).isoformat(),
        "end_date": _jd_to_date(sade_end_jd).isoformat(),
        "phase_start": phase_start_date,
        "phase_end": phase_end_date,
        "phases": phases,
        "interpretation_ready": True,
    }
