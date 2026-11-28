"""Draconic degree-in-sign is truncated, never rounded (1.1.0, 2026-11-28).

Until 1.1.0 the draconic chart stored ``int(round(x)) % 30`` while the sign
came from the unrounded longitude, so 29°40' Capricorn came out as
"Capricorn 0°" — the start of the sign the point is about to leave. Every
other place that prints a whole degree (the report graphics, ``fmt``)
truncates, so 29°40' is "29°" and 8°40' is "8°".

Bare dates at 12:00 UTC; the expected values were read from the engine and
checked against ``draconic_longitude``.
"""

from __future__ import annotations

import math
from datetime import date, time, timedelta

import pytest

from eldermind_core.services.ephemeris import (
    compute_draconic_chart,
    compute_julian_day_ut,
)


def _point(day: date, name: str) -> dict:
    jd_ut, _ = compute_julian_day_ut(day, time(12, 0), "UTC")
    return next(p for p in compute_draconic_chart(jd_ut)["planets"] if p["name"] == name)


@pytest.mark.parametrize(
    ("day", "name", "sign", "degree"),
    [
        # 29°30'-29°59': the old rounding gave 0° of the same sign.
        (date(1990, 1, 10), "Mars", "Capricorn", 29),  # 29°44'
        (date(1990, 2, 5), "Sun", "Pisces", 29),  # 29°56'
        (date(1990, 1, 2), "Moon", "Aries", 29),  # 29°56'
        # 0°00'-0°29': 0° before and after.
        (date(1990, 1, 10), "Mercury", "Pisces", 0),  # 0°02'
        (date(1990, 2, 9), "Moon", "Libra", 0),  # 0°17'
        (date(1990, 1, 7), "Sun", "Pisces", 0),  # 0°06'
        # x°30'-x°59' inside the sign: rounding went one degree up.
        (date(1990, 1, 15), "Moon", "Scorpio", 0),  # 0°55'
    ],
)
def test_draconic_degree_is_truncated(day: date, name: str, sign: str, degree: int) -> None:
    point = _point(day, name)
    assert point["sign"] == sign
    assert point["degree_in_sign"] == degree


def test_draconic_degree_matches_longitude_over_two_months() -> None:
    """For every body on 60 consecutive days: degree = floor(longitude mod 30)
    and the sign is the one that longitude lies in."""
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    day = date(2001, 3, 1)
    checked = 0
    for _ in range(60):
        jd_ut, _ = compute_julian_day_ut(day, time(12, 0), "UTC")
        for point in compute_draconic_chart(jd_ut)["planets"]:
            longitude = point["draconic_longitude"]
            # The stored longitude is rounded to 6 decimals; skip the
            # (practically absent) case of a body within 1e-6° of a cusp.
            if abs(longitude / 30 - round(longitude / 30)) * 30 < 1e-5:
                continue
            assert isinstance(point["degree_in_sign"], int)
            assert point["degree_in_sign"] == math.floor(longitude % 30)
            assert point["sign"] == signs[int(longitude // 30)]
            checked += 1
        day += timedelta(days=1)
    # 10 bodies x 60 days; the Node itself is skipped (it is 0° Aries by
    # construction, exactly on the cusp).
    assert checked == 600
