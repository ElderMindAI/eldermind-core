"""The single place where "today" is allowed to enter a calculation (bloker B1).

Before this module, `date.today()` sat inside three services. The consequence was
that the same birth data returned a different answer tomorrow — which makes the
result impossible to cache, impossible to golden-test, and impossible to promise
in an SLA.

Now every date-dependent service takes an explicit `reference_date`, and the only
fallback to the wall clock happens here, in UTC. The public API always passes the
value through, so a client that pins `reference_date` gets a byte-identical
answer forever.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from eldermind_core.core.errors import DateOutOfRangeError

#: Range the Swiss Ephemeris is trusted for in this product (bloker B7). The
#: library itself reaches much further, but outside this window we neither test
#: nor support the result — better a clear error than a confident wrong number.
MIN_SUPPORTED_DATE = date(1800, 1, 1)
MAX_SUPPORTED_DATE = date(2200, 12, 31)


def today_utc() -> date:
    """Current date in UTC.

    UTC rather than local time so that two servers in different regions agree on
    what "today" means, and so cache entries expire coherently at midnight UTC.
    """
    return datetime.now(timezone.utc).date()


def resolve_reference_date(reference_date: date | None) -> date:
    """Return the reference date to compute against, defaulting to today (UTC)."""
    return today_utc() if reference_date is None else reference_date


def assert_date_in_range(value: date, *, field: str = "birth_date") -> None:
    """Reject dates outside the supported ephemeris window (bloker B7).

    Raises:
        DateOutOfRangeError: With a message that names the actual bounds, so the
            caller does not have to read the docs to find out what went wrong.
    """
    if not MIN_SUPPORTED_DATE <= value <= MAX_SUPPORTED_DATE:
        raise DateOutOfRangeError(
            f"Date {value.isoformat()} is outside the supported range "
            f"{MIN_SUPPORTED_DATE.isoformat()}..{MAX_SUPPORTED_DATE.isoformat()}.",
            field=field,
        )


__all__ = [
    "MAX_SUPPORTED_DATE",
    "MIN_SUPPORTED_DATE",
    "assert_date_in_range",
    "resolve_reference_date",
    "today_utc",
]
