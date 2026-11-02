"""Sade-Sati calculation for Vedic astrology.

Sade-Sati is the 7.5-year period during which Saturn transits the twelfth,
first and second signs from the natal Moon sign. It is divided into three
phases of roughly 2.5 years each:

* Rising    – Saturn in the 12th sign from the Moon
* Peak      – Saturn in the same sign as the Moon
* Setting   – Saturn in the 2nd sign from the Moon

All calculations use the Lahiri (Chitra Paksha) ayanamsa.
"""

import copy
from datetime import date, datetime, timedelta
from typing import Final

import swisseph as swe

from eldermind_core.core.config import PLANET_IDS, ZODIAC_SIGNS
from eldermind_core.core.reference import resolve_reference_date

# Saturn spends roughly 2.5 years in each sign.
SATURN_DAYS_PER_SIGN: Final[float] = 365.25 * 2.5

# Bracket step used when searching for sign ingresses.
_SEARCH_STEP_DAYS: Final[float] = 5.0

# Search horizon in years when looking backward/forward for a Sade-Sati window.
#
# Must exceed one full Saturn revolution (~29.46 years). At 20 years the search
# silently failed for any Moon sign whose next window lay further out than that
# — on 2026-07-31 that was Capricorn, whose next transit of Sagittarius is in
# 2049. The whole Vedic section (and, through it, the report) died with a
# RuntimeError for roughly one client in twelve. Caught by the golden suite.
_SEARCH_HORIZON_YEARS: Final[float] = 32.0

_PHASE_ORDER: Final[list[str]] = ["rising", "peak", "setting"]

# How far past the birth date `cycles` reaches. Three Saturn revolutions.
LIFESPAN_YEARS: Final[float] = 90.0

# Saturn's fastest geocentric motion is about 0.13 deg/day: a jump of
# (distance to the boundary) / 0.14 days can never carry it across unseen.
_SATURN_MAX_SPEED: Final[float] = 0.14

# A retrograde loop can carry Saturn across a sign boundary three times; the
# crossings of one loop lie well within this span after the first, the next
# loop's are 29 years away. For an Aquarius Moon Saturn leaves Pisces (the
# setting sign) on 2027-06-02, is back in it from 2027-10-20 and leaves for
# good on 2028-02-23 — which is when that Sade-Sati really ends. Until 1.0.6
# only the first exit existed, and a report called it the definitive end.
_RETROGRADE_SPAN_DAYS: Final[float] = 400.0

# Saturn's retrograde arc is about 7°: once it stands further than this from a
# boundary, the loop that crossed it is over and the scan can stop.
_LOOP_REACH_DEGREES: Final[float] = 8.5


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
    tolerance_days: float = 1e-6,
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
        if hi - lo < tolerance_days:
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


def _next_ingress(source_sign: int, target_sign: int, start_jd: float, limit_jd: float) -> float | None:
    """First crossing from `source_sign` into `target_sign` after `start_jd`.

    Same answer as `_find_ingress(..., forward=True)`, without walking every
    five days: far from the boundary it jumps as far as Saturn could possibly
    travel. A lifetime of windows by the five-day walk cost ~0.9 s of CPU per
    chart; this takes a few dozen ephemeris calls per window.
    """
    boundary = target_sign * 30.0
    jd = start_jd
    longitude = _saturn_sidereal_longitude(jd)
    while jd <= limit_jd:
        step = max(((boundary - longitude) % 360.0) / _SATURN_MAX_SPEED, _SEARCH_STEP_DAYS)
        probe = jd + step
        probe_longitude = _saturn_sidereal_longitude(probe)
        if int(longitude // 30.0) % 12 == source_sign and int(probe_longitude // 30.0) % 12 == target_sign:
            return _refine_ingress(target_sign, jd, probe)
        jd, longitude = probe, probe_longitude
    return None


def _first_of_loop(source_sign: int, target_sign: int, crossing_jd: float) -> float:
    """The first crossing from `source_sign` into `target_sign` in the loop that made `crossing_jd`.

    A backward search finds the most recent crossing. For an Aquarius Moon the
    peak then began on 2023-01-17, Saturn's final entry into Aquarius, while
    `cycles` (searching forward) began it on 2022-04-29, the first — and a
    report quoted both. Every phase now starts at the first entry; `segments`
    carries the back-and-forth.
    """
    first = crossing_jd
    jd = crossing_jd - 1.0
    later = _offset(jd, target_sign)
    while later > -_LOOP_REACH_DEGREES and jd > crossing_jd - _RETROGRADE_SPAN_DAYS:
        earlier_jd = jd - _safe_step(later)
        earlier = _offset(earlier_jd, target_sign)
        if earlier < 0.0 <= later:  # an earlier entry into target_sign
            first = _refine_ingress(target_sign, earlier_jd, jd)
        jd, later = earlier_jd, earlier
    return first


def _offset(jd: float, target_sign: int) -> float:
    """Degrees Saturn stands past the start of `target_sign` (negative: not in it yet)."""
    return (_saturn_sidereal_longitude(jd) - target_sign * 30.0 + 180.0) % 360.0 - 180.0


def _safe_step(offset: float) -> float:
    """The longest step in which Saturn, `offset` degrees from a boundary, cannot reach it."""
    return max(abs(offset) / _SATURN_MAX_SPEED, _SEARCH_STEP_DAYS)


def _loop_crossings(source_sign: int, target_sign: int, first_jd: float) -> list[tuple[float, int]]:
    """Every crossing of one sign boundary, either way, in the loop that starts at `first_jd`.

    `target_sign` follows `source_sign`. Returns ``(moment, sign entered)`` in
    time order, the first crossing included as given. The later ones are
    refined to ~9 seconds: they are reported as dates.
    """
    crossings: list[tuple[float, int]] = [(first_jd, target_sign)]
    jd = first_jd + 0.01
    before = max(_offset(jd, target_sign), 0.0)
    while before < _LOOP_REACH_DEGREES and jd < first_jd + _RETROGRADE_SPAN_DAYS:
        probe = jd + _safe_step(before)
        after = _offset(probe, target_sign)
        if (before < 0.0) != (after < 0.0):
            entered = target_sign if after >= 0.0 else source_sign
            crossings.append((_refine_ingress(entered, jd, probe, tolerance_days=1e-4), entered))
        jd, before = probe, after
    return crossings


def _segments(signs: list[int], moments: list[float]) -> tuple[list[list[tuple[float, float]]], float]:
    """Every stay of Saturn in each phase sign, and its final exit from the setting sign.

    `signs` are the rising, peak, setting and following sign; `moments` the
    first crossing into each of them. The window opens at the first entry into
    the rising sign and closes at the last crossing into the following one, so
    a retrograde return into the setting sign extends it.
    """
    before = (signs[0] - 1) % 12
    events = sorted(
        crossing
        for source, target, first in zip([before, *signs[:3]], signs, moments)
        for crossing in _loop_crossings(source, target, first)
    )
    stays: list[list[tuple[float, float]]] = [[], [], []]
    inside: int | None = None
    opened = 0.0
    for moment, entered in events:
        if inside is not None:
            stays[inside].append((opened, moment))
            inside = None
        if entered in signs[:3]:
            inside, opened = signs.index(entered), moment
    final_exit = max(moment for moment, entered in events if entered == signs[3])
    return stays, final_exit


def _phase_list(signs: list[int], moments: list[float]) -> tuple[list[dict], float]:
    """The three phases from four first-crossing moments (rising, peak, setting, end).

    Each phase also lists its `segments`: one per stay of Saturn in the sign,
    retrograde returns included. Returns the phases and the final exit.
    """
    stays, final_exit = _segments(signs, moments)
    phases = [
        {
            "phase": _PHASE_ORDER[index],
            "sign": ZODIAC_SIGNS[signs[index]],
            "start": _jd_to_date(moments[index]).isoformat(),
            "end": _jd_to_date(moments[index + 1]).isoformat(),
            "segments": [
                {"start": _jd_to_date(start).isoformat(), "end": _jd_to_date(end).isoformat()}
                for start, end in stays[index]
            ],
        }
        for index in range(3)
    ]
    return phases, final_exit


def _lifetime_cycles(
    moon_index: int,
    birth_date: date,
    current_start: str,
    status: str,
    reference_date: date,
    lifespan_years: float,
) -> list[dict]:
    """Every Sade-Sati window from birth to `lifespan_years`, oldest first.

    Until 1.0.4 only the current or next window existed, so a reading that
    mentioned the previous one invented its years ("2009-2017" for a window
    that ran 2011-11-15 to 2020-01-24). The windows are found by the same
    ingress chain as the top-level fields, so the one those fields describe
    appears here with identical dates; `relation` places each window against
    the reference date: past, previous, current, next or future.
    """
    sign_12 = (moon_index - 1) % 12
    signs = [sign_12, moon_index, (moon_index + 1) % 12, (moon_index + 2) % 12]
    birth_jd = _date_to_jd(birth_date)
    horizon_jd = birth_jd + lifespan_years * 365.25

    found: list[list[float]] = []
    # Start one search horizon before birth: a window may be under way at birth.
    jd = birth_jd - _SEARCH_HORIZON_YEARS * 365.25
    while True:
        rising = _next_ingress((sign_12 - 1) % 12, sign_12, jd, horizon_jd)
        if rising is None or rising > horizon_jd:
            break
        moments = [rising]
        for source, target in zip(signs[:3], signs[1:]):
            nxt = _next_ingress(source, target, moments[-1], moments[-1] + _SEARCH_HORIZON_YEARS * 365.25)
            if nxt is None:
                break
            moments.append(nxt)
        if len(moments) < 4:
            break
        if moments[-1] > birth_jd:
            found.append(moments)
        jd = moments[-1]

    cycles = []
    for m in found:
        phases, final_exit = _phase_list(signs, m)
        cycles.append({
            "relation": None,
            "start_date": _jd_to_date(m[0]).isoformat(),
            "end_date": _jd_to_date(m[3]).isoformat(),
            "final_end_date": _jd_to_date(final_exit).isoformat(),
            "age_at_start": round(max(m[0] - birth_jd, 0.0) / 365.25, 1),
            "age_at_end": round((m[3] - birth_jd) / 365.25, 1),
            "age_at_final_end": round((final_exit - birth_jd) / 365.25, 1),
            "phases": phases,
        })

    anchor = next(
        (i for i, c in enumerate(cycles) if c["start_date"] == current_start), None
    )
    ref = reference_date.isoformat()
    for index, cycle in enumerate(cycles):
        if anchor is not None:
            if index == anchor:
                relation = "current" if status == "active" else "next"
            elif index == anchor - 1:
                relation = "previous"
            elif index < anchor:
                relation = "past"
            elif index == anchor + 1 and status == "active":
                relation = "next"
            else:
                relation = "future"
        elif cycle["start_date"] <= ref < cycle["end_date"]:
            relation = "current"
        elif cycle["end_date"] <= ref:
            later_done = any(c["end_date"] <= ref for c in cycles[index + 1:])
            relation = "past" if later_done else "previous"
        else:
            earlier_ahead = any(c["start_date"] > ref for c in cycles[:index])
            relation = "future" if earlier_ahead else "next"
        cycle["relation"] = relation
    return cycles


def compute_sade_sati(
    moon_sign: str,
    reference_date: date | None = None,
    birth_date: date | None = None,
    *,
    lifespan_years: float = LIFESPAN_YEARS,
) -> dict:
    """Compute the Sade-Sati status for a given natal Moon sign.

    Args:
        moon_sign: Sidereal zodiac sign occupied by the natal Moon.
        reference_date: Date used to determine whether Sade-Sati is active.
            Defaults to today.
        birth_date: When given, `cycles` lists every window of the life
            (see `_lifetime_cycles`).
        lifespan_years: How far past birth `cycles` reaches.

    Returns:
        Dictionary with status, phase, phase dates and a breakdown of the
        three Sade-Sati phases. Dates are ISO strings for JSON compatibility.
    """
    reference_date = resolve_reference_date(reference_date)

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

        # Backward searches return the latest crossing of a loop; each is moved
        # to the loop's first, so these phases match `cycles` (_first_of_loop).
        if phase_index == 0:  # rising
            rising_start_jd = _find_ingress(
                (sign_12 - 1) % 12, sign_12, ref_jd, forward=False
            )
            if rising_start_jd:
                rising_start_jd = _first_of_loop((sign_12 - 1) % 12, sign_12, rising_start_jd)
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
            if peak_start_jd:
                peak_start_jd = _first_of_loop(sign_12, sign_1, peak_start_jd)
            rising_start_jd = (
                _find_ingress((sign_12 - 1) % 12, sign_12, peak_start_jd, forward=False)
                if peak_start_jd
                else None
            )
            if rising_start_jd:
                rising_start_jd = _first_of_loop((sign_12 - 1) % 12, sign_12, rising_start_jd)
            setting_start_jd = (
                _find_ingress(sign_1, sign_2, peak_start_jd, forward=True)
                if peak_start_jd
                else None
            )
        else:  # setting
            setting_start_jd = _find_ingress(sign_1, sign_2, ref_jd, forward=False)
            if setting_start_jd:
                setting_start_jd = _first_of_loop(sign_1, sign_2, setting_start_jd)
            peak_start_jd = (
                _find_ingress(sign_12, sign_1, setting_start_jd, forward=False)
                if setting_start_jd
                else None
            )
            if peak_start_jd:
                peak_start_jd = _first_of_loop(sign_12, sign_1, peak_start_jd)
            rising_start_jd = (
                _find_ingress((sign_12 - 1) % 12, sign_12, peak_start_jd, forward=False)
                if peak_start_jd
                else None
            )
            if rising_start_jd:
                rising_start_jd = _first_of_loop((sign_12 - 1) % 12, sign_12, rising_start_jd)
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

    status = "active" if sade_sati_active else "inactive"
    start_date = _jd_to_date(rising_start_jd).isoformat()
    cycles = (
        _lifetime_cycles(moon_index, birth_date, start_date, status, reference_date, lifespan_years)
        if birth_date is not None
        else None
    )
    # The window described here is one of `cycles`, found by the same chain of
    # first entries: take its phases instead of scanning the loops twice.
    same = next((c for c in cycles or [] if c["start_date"] == start_date), None)
    if same is not None:
        phases = copy.deepcopy(same["phases"])
        final_end_date = same["final_end_date"]
    else:
        phases, final_exit_jd = _phase_list(
            [sign_12, sign_1, sign_2, sign_3],
            [rising_start_jd, peak_start_jd, setting_start_jd, sade_end_jd],
        )
        final_end_date = _jd_to_date(final_exit_jd).isoformat()

    phase_start_date = None
    phase_end_date = None
    if sade_sati_active and phase_index is not None:
        phase_start_date = phases[phase_index]["start"]
        phase_end_date = phases[phase_index]["end"]

    result = {
        "status": status,
        "phase": current_phase_name,
        "moon_sign": moon_sign,
        "saturn_sign": ZODIAC_SIGNS[current_saturn_sign],
        "start_date": start_date,
        "end_date": _jd_to_date(sade_end_jd).isoformat(),
        # end_date is Saturn's first exit from the setting sign; after a
        # retrograde return the window really closes here.
        "final_end_date": final_end_date,
        "phase_start": phase_start_date,
        "phase_end": phase_end_date,
        "phases": phases,
        "interpretation_ready": True,
    }
    if cycles is not None:
        result["cycles"] = cycles
    return result
