"""Geocoding + timezone resolution — Faza F6.5.

Converts a free-text birth place (as typed by the client, e.g. "Warszawa,
Polska") plus local date/time into precise coordinates, an IANA timezone
name, and the equivalent UTC datetime — everything the calculation engine
(Swiss Ephemeris) needs, without requiring the client to know their own
coordinates.

Providers (no API key required):
  - Nominatim (OpenStreetMap) for geocoding, via `geopy`.
  - `timezonefinder` for offline lat/lon -> IANA timezone lookup (no network
    call, no rate limit).
  - `zoneinfo` (stdlib) + the resolved IANA name to build a DST-aware UTC
    datetime from the local date/time (correctly handles e.g. Polish summer
    time changes across the years).
"""

from __future__ import annotations

import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

USER_AGENT = "eldermind-report-engine/1.0"

# Be a good citizen of the free Nominatim public instance: max 1 req/sec,
# small retry budget with a pause between attempts.
NOMINATIM_MAX_RETRIES = 3
NOMINATIM_RETRY_DELAY_SECONDS = 1.0

_geolocator = Nominatim(user_agent=USER_AGENT)
_timezone_finder = TimezoneFinder()


class LocationResolutionError(RuntimeError):
    """Raised when the birth place can't be geocoded or timezone can't be resolved.

    This is the client-input-facing error: the worker should catch it and
    mark the order `failed` with a clear, non-technical message rather than
    burning LLM credits on invalid/incomplete birth data.
    """


@dataclass(frozen=True)
class ResolvedLocation:
    """Everything the engine needs, derived from a free-text birth place."""

    latitude: float
    longitude: float
    timezone: str
    utc_datetime: datetime


def _geocode_birth_place(birth_place: str) -> tuple[float, float]:
    """Resolve a free-text place name to (latitude, longitude) via Nominatim.

    Retries a few times on transient network/service errors (with a
    respectful delay between attempts), but raises `LocationResolutionError`
    immediately if Nominatim simply can't find the place at all.
    """
    if not birth_place or not birth_place.strip():
        raise LocationResolutionError("Miejsce urodzenia jest puste.")

    last_error: Exception | None = None
    for attempt in range(1, NOMINATIM_MAX_RETRIES + 1):
        try:
            location = _geolocator.geocode(birth_place, timeout=10)
            break
        except (GeocoderTimedOut, GeocoderServiceError) as exc:
            last_error = exc
            if attempt < NOMINATIM_MAX_RETRIES:
                time_module.sleep(NOMINATIM_RETRY_DELAY_SECONDS)
    else:
        raise LocationResolutionError(
            f"Nie udało się skontaktować z usługą geokodowania dla '{birth_place}': {last_error}"
        ) from last_error

    if location is None:
        raise LocationResolutionError(
            f"Nie znaleziono lokalizacji dla podanego miejsca urodzenia: '{birth_place}'."
        )

    return location.latitude, location.longitude


def _resolve_timezone(latitude: float, longitude: float) -> str:
    """Offline lat/lon -> IANA timezone name lookup (no network call)."""
    tz_name = _timezone_finder.timezone_at(lng=longitude, lat=latitude)
    if tz_name is None:
        raise LocationResolutionError(
            f"Nie udało się ustalić strefy czasowej dla współrzędnych ({latitude}, {longitude})."
        )
    return tz_name


def _build_utc_datetime(local_date: date, local_time: time, tz_name: str) -> datetime:
    """Attach the resolved IANA timezone to the local date/time and convert to UTC.

    Using `zoneinfo` (not a fixed UTC offset) ensures historical DST rules
    are respected — e.g. Poland observed summer time in 1993.
    """
    try:
        tzinfo = ZoneInfo(tz_name)
    except Exception as exc:  # noqa: BLE001 - unknown/invalid IANA name
        raise LocationResolutionError(f"Nieprawidłowa strefa czasowa: '{tz_name}'.") from exc

    local_dt = datetime.combine(local_date, local_time, tzinfo=tzinfo)
    return local_dt.astimezone(ZoneInfo("UTC"))


def resolve_location_and_time(
    birth_place: str,
    local_date: date,
    local_time: time,
) -> ResolvedLocation:
    """Resolve a free-text birth place + local date/time into engine-ready data.

    Args:
        birth_place: Free-text location as typed by the client, e.g.
            "Warszawa, Polska".
        local_date: Local birth date.
        local_time: Local birth time.

    Returns:
        `ResolvedLocation` with latitude, longitude, IANA timezone name, and
        the equivalent UTC datetime.

    Raises:
        LocationResolutionError: If the place can't be geocoded, or a
            timezone can't be determined for the resolved coordinates.
    """
    latitude, longitude = _geocode_birth_place(birth_place)
    tz_name = _resolve_timezone(latitude, longitude)
    utc_dt = _build_utc_datetime(local_date, local_time, tz_name)

    return ResolvedLocation(
        latitude=latitude,
        longitude=longitude,
        timezone=tz_name,
        utc_datetime=utc_dt,
    )
