"""Panchanga elements of the birth moment: tithi, paksha and the lunar phase.

The report used to leave these to the model, which counted them itself: one
reading put a birth "a day and a half before the new moon" when the ephemeris
says 2.2 days, another named the tithi from a guessed angle. Everything here
comes from the Sun–Moon elongation, which is the same in the tropical and the
sidereal zodiac, so no ayanamsa is involved.
"""

from __future__ import annotations

from typing import Final

import swisseph as swe

TITHI_DEGREES: Final[float] = 12.0

# Tithi names within a paksha; the 15th is Purnima (Shukla) or Amavasya (Krishna).
TITHI_NAMES: Final[list[str]] = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi",
]

# Mean daily gain of the Moon on the Sun, used only as the Newton step.
_MEAN_SYNODIC_SPEED: Final[float] = 360.0 / 29.530588


def _elongation(jd_ut: float) -> float:
    sun, _ = swe.calc_ut(jd_ut, swe.SUN, 0)
    moon, _ = swe.calc_ut(jd_ut, swe.MOON, 0)
    return (float(moon[0]) - float(sun[0])) % 360.0


def _phase_moment(jd_ut: float, target: float, *, forward: bool) -> float:
    """Julian Day of the nearest moment the elongation equals `target`."""
    gap = (target - _elongation(jd_ut)) % 360.0 if forward else -((_elongation(jd_ut) - target) % 360.0)
    jd = jd_ut + gap / _MEAN_SYNODIC_SPEED
    for _ in range(30):
        delta = (target - _elongation(jd) + 180.0) % 360.0 - 180.0
        if abs(delta) < 1e-7:
            break
        jd += delta / _MEAN_SYNODIC_SPEED
    return jd


def tithi_from_elongation(elongation: float) -> dict:
    """Tithi number (1-30), its name and the paksha for a Sun–Moon elongation."""
    number = int((elongation % 360.0) // TITHI_DEGREES) + 1
    paksha = "Shukla" if number <= 15 else "Krishna"
    day = number if number <= 15 else number - 15
    if day == 15:
        name = "Purnima" if paksha == "Shukla" else "Amavasya"
    else:
        name = TITHI_NAMES[day - 1]
    return {"tithi_number": number, "tithi_name": name, "paksha": paksha}


def compute_panchanga(jd_ut: float) -> dict:
    """Tithi, paksha and the distance in days to the surrounding new and full moons."""
    elongation = _elongation(jd_ut)
    result = {"elongation": round(elongation, 3), **tithi_from_elongation(elongation)}
    result.update(
        {
            "days_since_new_moon": round(jd_ut - _phase_moment(jd_ut, 0.0, forward=False), 2),
            "days_to_new_moon": round(_phase_moment(jd_ut, 0.0, forward=True) - jd_ut, 2),
            "days_since_full_moon": round(jd_ut - _phase_moment(jd_ut, 180.0, forward=False), 2),
            "days_to_full_moon": round(_phase_moment(jd_ut, 180.0, forward=True) - jd_ut, 2),
        }
    )
    return result


__all__ = ["TITHI_NAMES", "compute_panchanga", "tithi_from_elongation"]
