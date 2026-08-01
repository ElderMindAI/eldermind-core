"""Typed errors raised by the calculation engine (bloker B4).

A public API cannot answer every failure with `500 CALCULATION_ERROR` — the
caller has no way to tell "you gave me a timezone that does not exist" from "our
server fell over". Each class here carries a stable `code` that the HTTP layer
maps straight onto the error contract in §3.6 of the product plan.

Everything derives from `ValueError`. That is deliberate: the report backend
already catches `ValueError` around `compute_julian_day_ut` and turns it into a
400, so introducing these types changes nothing for the live product.
"""

from __future__ import annotations


class EldermindCoreError(ValueError):
    """Base class for every error the engine raises on bad input.

    Attributes:
        code: Stable machine-readable identifier, mirrored in the HTTP contract.
        field: Name of the offending input field, when a single field is at fault.
    """

    code: str = "CALCULATION_ERROR"
    field: str | None = None

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if field is not None:
            self.field = field

    def to_dict(self) -> dict[str, str | None]:
        """Shape used verbatim by the API error envelope."""
        return {"code": self.code, "message": self.message, "field": self.field}


class InvalidTimezoneError(EldermindCoreError):
    """The supplied string is not a known IANA timezone."""

    code = "INVALID_TIMEZONE"
    field = "timezone"


class AmbiguousLocalTimeError(EldermindCoreError):
    """The local time occurs twice — the autumn DST overlap.

    Both readings are valid wall-clock times, so the engine refuses to guess in
    strict mode. The caller must disambiguate (or accept the earlier reading).
    """

    code = "AMBIGUOUS_LOCAL_TIME"
    field = "birth_time"


class NonexistentLocalTimeError(EldermindCoreError):
    """The local time never happened — the spring DST gap.

    Clocks jumped straight over it, so no instant maps to this wall-clock time.
    """

    code = "AMBIGUOUS_LOCAL_TIME"
    field = "birth_time"


class DateOutOfRangeError(EldermindCoreError):
    """The date falls outside the range the ephemeris is trusted for (bloker B7)."""

    code = "DATE_OUT_OF_RANGE"
    field = "birth_date"


class HouseSystemUnavailableError(EldermindCoreError):
    """The requested house system is undefined at this latitude.

    Placidus divides the diurnal arc, which degenerates beyond the polar
    circles — a body can stay above the horizon for weeks, so there is no arc to
    divide. This is mathematics, not a bug, so the caller is told to pick a
    system that does work there rather than being handed a 500.
    """

    code = "HOUSE_SYSTEM_UNAVAILABLE"
    field = "house_system"


class GeocodingFailedError(EldermindCoreError):
    """The place name could not be resolved to coordinates and a timezone."""

    code = "GEOCODING_FAILED"
    field = "birth_place"


class CalculationError(EldermindCoreError):
    """A system failed to compute for a reason that is not the caller's fault."""

    code = "CALCULATION_ERROR"


__all__ = [
    "AmbiguousLocalTimeError",
    "CalculationError",
    "DateOutOfRangeError",
    "EldermindCoreError",
    "GeocodingFailedError",
    "HouseSystemUnavailableError",
    "InvalidTimezoneError",
    "NonexistentLocalTimeError",
]
