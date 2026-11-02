"""Low-level astronomical calculations backed by pyswisseph (Swiss Ephemeris).

All coordinate conversions and house calculations are performed locally
without external API calls.
"""

from datetime import date, datetime, timedelta, time, tzinfo
from typing import Tuple
from zoneinfo import ZoneInfo, available_timezones

import swisseph as swe

from eldermind_core.core.config import (
    ASPECT_DEFINITIONS,
    DEGREES_PER_SIGN,
    DEFAULT_ORB_DEGREES,
    HOUSE_SYSTEM_CODES,
    HOUSE_SYSTEM_WESTERN,
    NAKSHATRA_BODIES,
    NAKSHATRA_COUNT,
    NAKSHATRA_DEGREES,
    NAKSHATRA_NAMES,
    PADA_COUNT,
    PADA_DEGREES,
    PLANET_IDS,
    SIGNS_COUNT,
    ZODIAC_SIGNS,
)
from eldermind_core.core.errors import (
    AmbiguousLocalTimeError,
    HouseSystemUnavailableError,
    InvalidTimezoneError,
    NonexistentLocalTimeError,
)
from eldermind_core.core.reference import assert_date_in_range
from eldermind_core.services.panchanga import compute_panchanga
from eldermind_core.services.vedic_dasha import (
    VIMSHOTTARI_ORDER,
    compute_avakahada_chakra,
    compute_vimshottari_dasha,
)
from eldermind_core.services.sade_sati import compute_sade_sati
from eldermind_core.services.transits import (
    EXACT_ORB,
    NODE_CLUSTER_DAYS,
    aspect_orb,
    bisect_change,
    cluster,
    jd_to_date,
    jd_to_moment,
    julian_day_at_noon,
    local_minima,
    longitude_speed,
    merge_node_passes,
    minimize,
    separation,
    sign_index,
    sign_of,
    tropical_longitude,
)
from eldermind_core.services.vedic_yogas import (
    attach_vedic_houses,
    compute_drishti,
    compute_yogas,
    ketu_position,
)


def _assert_valid_timezone(timezone_name: str) -> None:
    """Validate that the supplied timezone name is a known IANA zone."""
    if timezone_name not in available_timezones():
        raise InvalidTimezoneError(f"Unknown or unsupported timezone: {timezone_name!r}")


def describe_local_time_anomaly(local_dt: datetime) -> str | None:
    """Return a human-readable note if this wall-clock time is not well-defined.

    Two things can go wrong around a daylight-saving transition:

    * **Gap** (spring forward) — the time never existed; no instant maps to it.
    * **Fold** (autumn back) — the time happened twice, an hour apart.

    `zoneinfo` silently picks a reading in both cases rather than complaining, so
    without this check a birth time inside a DST transition yields a confidently
    wrong chart. Returns ``None`` when the time is unambiguous.
    """
    # Round-tripping through UTC lands somewhere else only for gap times.
    if local_dt.astimezone(ZoneInfo("UTC")).astimezone(local_dt.tzinfo) != local_dt:
        return (
            f"Local time {local_dt.time().isoformat()} on "
            f"{local_dt.date().isoformat()} does not exist in "
            f"{local_dt.tzinfo} (daylight-saving gap)."
        )

    if local_dt.replace(fold=0).utcoffset() != local_dt.replace(fold=1).utcoffset():
        return (
            f"Local time {local_dt.time().isoformat()} on "
            f"{local_dt.date().isoformat()} occurs twice in "
            f"{local_dt.tzinfo} (daylight-saving overlap)."
        )

    return None


def _local_to_utc(
    birth_date: date,
    birth_time: time,
    timezone_name: str,
    *,
    strict: bool = False,
) -> datetime:
    """Convert a local birth date/time to UTC using the IANA timezone database.

    Args:
        strict: When true, refuse to guess through a daylight-saving transition
            and raise instead. The public API sets this; the report product does
            not, so its behaviour is unchanged.

    Raises:
        InvalidTimezoneError: The timezone name is not a known IANA zone.
        AmbiguousLocalTimeError: Strict mode, and the time occurs twice.
        NonexistentLocalTimeError: Strict mode, and the time never happened.
    """
    _assert_valid_timezone(timezone_name)
    tz: tzinfo = ZoneInfo(timezone_name)

    try:
        local_dt = datetime(
            year=birth_date.year,
            month=birth_date.month,
            day=birth_date.day,
            hour=birth_time.hour,
            minute=birth_time.minute,
            second=birth_time.second,
            microsecond=birth_time.microsecond,
            tzinfo=tz,
        )
    except Exception as exc:  # pragma: no cover - defensive catch for malformed dates
        raise ValueError(f"Unable to build local datetime: {exc}") from exc

    if strict:
        anomaly = describe_local_time_anomaly(local_dt)
        if anomaly is not None:
            error = (
                NonexistentLocalTimeError
                if "does not exist" in anomaly
                else AmbiguousLocalTimeError
            )
            raise error(anomaly)

    return local_dt.astimezone(ZoneInfo("UTC"))


def _utc_to_julian_day_ut(utc_dt: datetime) -> float:
    """Convert a UTC datetime to Julian Day in Universal Time.

    pyswisseph expects the hour argument as a fractional UT hour.
    """
    fractional_hour = (
        utc_dt.hour
        + utc_dt.minute / 60.0
        + utc_dt.second / 3600.0
        + utc_dt.microsecond / 3_600_000_000.0
    )
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, fractional_hour)


def _longitude_to_zodiac(longitude: float) -> Tuple[str, float]:
    """Convert a tropical longitude to a zodiac sign and degree-in-sign."""
    normalized = longitude % 360.0
    sign_index = int(normalized // DEGREES_PER_SIGN) % SIGNS_COUNT
    degree_in_sign = normalized - (sign_index * DEGREES_PER_SIGN)
    return ZODIAC_SIGNS[sign_index], degree_in_sign


def _house_system_code() -> bytes:
    """Return the Placidus house system identifier understood by pyswisseph.

    The installed binding expects a single-character byte string (e.g. b'P')
    for the house system parameter of ``swe.houses_ex``.
    """
    return HOUSE_SYSTEM_WESTERN


def _apply_ayanamsa_mode() -> None:
    """Set the sidereal mode to Lahiri (Chitra Paksha) for Vedic calculations.

    This is a global Swiss Ephemeris setting. It affects all subsequent
    calls that request sidereal positions, so we configure it once.
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI)


def compute_julian_day_ut(
    birth_date: date,
    birth_time: time,
    timezone_name: str,
    *,
    strict: bool = False,
) -> Tuple[float, datetime]:
    """Convert local birth data to UTC and compute the Julian Day (UT).

    Args:
        strict: Refuse ambiguous or non-existent local times instead of silently
            picking a reading. See `_local_to_utc`.

    Returns:
        A tuple of (julian_day_ut, utc_datetime).

    Raises:
        DateOutOfRangeError: The date is outside the supported window (B7).
        InvalidTimezoneError: The timezone name is not a known IANA zone.
    """
    assert_date_in_range(birth_date)
    utc_dt = _local_to_utc(birth_date, birth_time, timezone_name, strict=strict)
    jd_ut = _utc_to_julian_day_ut(utc_dt)
    return jd_ut, utc_dt


def compute_planet_position(
    jd_ut: float,
    name: str,
    planet_id: int,
    *,
    sidereal: bool = False,
) -> dict:
    """Calculate the ecliptic longitude and retrograde status of a planet.

    Args:
        jd_ut: Julian Day in Universal Time.
        name: Canonical human-readable name of the planet/point.
        planet_id: pyswisseph identifier for the body.
        sidereal: If True, compute the longitude in the sidereal zodiac
            (Lahiri ayanamsa). Otherwise tropical.

    Returns:
        Dictionary matching the PlanetPosition schema.
    """
    flags = 0
    if sidereal:
        _apply_ayanamsa_mode()
        flags |= swe.FLG_SIDEREAL

    result, err = swe.calc_ut(jd_ut, planet_id, flags)
    if err:
        # Swiss Ephemeris can emit warnings in serr even when data is returned.
        # We surface them only when the result is missing.
        if not result:
            raise RuntimeError(f"Ephemeris calculation failed for {name}: {err}")

    longitude = float(result[0]) % 360.0
    # Longitude speed is at result index 3 for the default return set.
    # If speed is exactly zero (e.g. with certain flag combinations), fall back
    # to a small numerical derivative of the longitude to keep retrograde
    # detection reliable across pyswisseph builds.
    longitude_speed = float(result[3])
    if longitude_speed == 0.0:
        epsilon = 1.0 / 86400.0  # one second in days
        prev, _ = swe.calc_ut(jd_ut - epsilon, planet_id, flags)
        next_, _ = swe.calc_ut(jd_ut + epsilon, planet_id, flags)
        longitude_speed = (float(next_[0]) - float(prev[0])) / (2.0 * epsilon)

    sign, degree_in_sign = _longitude_to_zodiac(longitude)

    return {
        "name": name,
        "longitude": round(longitude, 6),
        "sign": sign,
        "degree_in_sign": round(degree_in_sign, 6),
        "is_retrograde": longitude_speed < 0.0,
    }


def compute_houses(
    jd_ut: float,
    latitude: float,
    longitude: float,
    *,
    sidereal: bool = False,
    house_system: str = "placidus",
) -> Tuple[dict, dict, list[dict]]:
    """Calculate houses, Ascendant and Midheaven.

    By default Placidus (Western) is used. When ``sidereal`` is True, the
    Lahiri ayanamsa is applied and the house cusps are returned in sidereal
    longitude.

    Args:
        jd_ut: Julian Day in Universal Time.
        latitude: Geographic latitude in decimal degrees.
        longitude: Geographic longitude in decimal degrees (positive east).
        sidereal: If True, compute sidereal positions using Lahiri ayanamsa.
        house_system: ``placidus`` or ``whole_sign``. Placidus fails beyond the
            polar circles — see `HouseSystemUnavailableError`.

    Returns:
        Tuple of (ascendant_dict, midheaven_dict, list_of_house_dicts).

    Raises:
        HouseSystemUnavailableError: The system is undefined at this latitude.
    """
    if sidereal:
        _apply_ayanamsa_mode()

    hsys = HOUSE_SYSTEM_CODES.get(house_system)
    if hsys is None:
        raise HouseSystemUnavailableError(
            f"Unknown house system {house_system!r}. "
            f"Supported: {', '.join(sorted(HOUSE_SYSTEM_CODES))}."
        )

    try:
        cusps, ascmc = swe.houses_ex(jd_ut, latitude, longitude, hsys, 0)
    except Exception as exc:
        # Swiss Ephemeris signals "cannot divide the diurnal arc" with a bare
        # error string. Left unhandled it surfaces as a 500 and the caller has
        # no idea their latitude is the problem.
        raise HouseSystemUnavailableError(
            f"House system {house_system!r} is undefined at latitude "
            f"{latitude:.4f}. Beyond the polar circles the diurnal arc does not "
            f"divide; use house_system='whole_sign', which is defined at every "
            f"latitude."
        ) from exc

    if sidereal:
        # ``swe.houses_ex`` returns tropical cusps even when called with
        # sidereal settings in some pyswisseph builds. Convert each cusp to
        # sidereal by subtracting the ayanamsa.
        ayanamsa = swe.get_ayanamsa(jd_ut)
        cusps = tuple((c - ayanamsa) % 360.0 for c in cusps)
        ascmc = tuple((a - ayanamsa) % 360.0 for a in ascmc)

    ascendant_lon = float(ascmc[0]) % 360.0
    midheaven_lon = float(ascmc[1]) % 360.0

    asc_sign, asc_deg = _longitude_to_zodiac(ascendant_lon)
    mc_sign, mc_deg = _longitude_to_zodiac(midheaven_lon)

    ascendant = {
        "name": "Ascendant",
        "longitude": round(ascendant_lon, 6),
        "sign": asc_sign,
        "degree_in_sign": round(asc_deg, 6),
        "is_retrograde": False,
    }

    midheaven = {
        "name": "Midheaven",
        "longitude": round(midheaven_lon, 6),
        "sign": mc_sign,
        "degree_in_sign": round(mc_deg, 6),
        "is_retrograde": False,
    }

    houses: list[dict] = []
    for house_number in range(1, 13):
        # pyswisseph returns cusps as a 12-element tuple indexed from 0.
        cusp_lon = float(cusps[house_number - 1]) % 360.0
        sign, deg = _longitude_to_zodiac(cusp_lon)
        houses.append(
            {
                "house_number": house_number,
                "longitude": round(cusp_lon, 6),
                "sign": sign,
                "degree_in_sign": round(deg, 6),
            }
        )

    return ascendant, midheaven, houses


def _which_house(longitude: float, house_cusps: list[dict]) -> int:
    """Return the Placidus house number containing a given longitude.

    Houses are numbered 1-12 by ascending cusp longitude. A point belongs to
    the house whose cusp it follows, up to (but not including) the next cusp.
    Wrap-around across 360° is handled by treating the zodiac as a circle.
    """
    sorted_cusps = sorted(
        ((c["longitude"], c["house_number"]) for c in house_cusps),
        key=lambda item: item[0],
    )
    longitudes = [c[0] for c in sorted_cusps]
    numbers = [c[1] for c in sorted_cusps]

    if not longitudes:
        raise ValueError("House cusps are required to determine house placement")

    # Find the last cusp that is <= the point's longitude (with wrap-around).
    for i in range(len(longitudes) - 1, -1, -1):
        cusp_lon = longitudes[i]
        if longitude >= cusp_lon:
            return numbers[i]

    # Longitude falls before the first cusp in ascending order => it belongs
    # to the last house (wrap around 360°).
    return numbers[-1]


def attach_houses_to_planets(
    planets: list[dict], house_cusps: list[dict]
) -> list[dict]:
    """Augment every planet/point with the Placidus house it occupies.

    Adds a ``house_number`` key to each planet dictionary. Used by the
    western tropical chart so downstream prompts never have to guess the
    house placement (e.g. for the Moon's Nodes).
    """
    updated: list[dict] = []
    for planet in planets:
        entry = dict(planet)
        entry["house_number"] = _which_house(planet["longitude"], house_cusps)
        updated.append(entry)
    return updated


def compute_all_planets(jd_ut: float, *, sidereal: bool = False) -> list[dict]:
    """Compute ecliptic positions for all configured planets and points."""
    return [
        compute_planet_position(jd_ut, name, planet_id, sidereal=sidereal)
        for name, planet_id in PLANET_IDS.items()
    ]


def compute_draconic_chart(jd_ut: float, house_cusps: list[dict] | None = None) -> dict:
    """Calculate the Draconic chart by shifting the tropical zodiac to the
    True North Node.

    In the Draconic system 0° Aries is aligned with the tropical longitude of
    the North Node. For every planet/point we subtract the Node's longitude and
    wrap to [0, 360).

    The output rounds positional data to whole degrees so prompts never contain
    misleading ``X°YY'`` values where YY > 59 (e.g. 8°91').

    Args:
        jd_ut: Julian Day in Universal Time.
        house_cusps: Natal Placidus cusps. When given, every point also gets
            ``house_number``: the natal house of the planet, the convention
            the report's draconic module reads against (the draconic Sun of a
            natal 6th-house Sun is "in the 6th"). Until 1.0.5 the model
            assigned these itself and put such a Sun in the 8th.

    Returns:
        Dictionary with the North Node longitude and a list of Draconic
        planetary positions.
    """
    north_node = compute_planet_position(jd_ut, "TrueNode", PLANET_IDS["TrueNode"])
    node_longitude = north_node["longitude"]

    draconic_points: list[dict] = []
    for name, planet_id in PLANET_IDS.items():
        tropical = compute_planet_position(jd_ut, name, planet_id)
        draconic_longitude = (tropical["longitude"] - node_longitude) % 360.0
        sign, degree_in_sign = _longitude_to_zodiac(draconic_longitude)
        point = {
            "name": name,
            "draconic_longitude": round(draconic_longitude, 6),
            "sign": sign,
            # Round to whole degrees to prevent LLM hallucinations like 8°91'.
            "degree_in_sign": int(round(degree_in_sign)) % 30,
            "tropical_longitude": round(tropical["longitude"], 6),
        }
        if house_cusps:
            point["house_number"] = _which_house(tropical["longitude"], house_cusps)
        draconic_points.append(point)

    return {
        "north_node_longitude": round(node_longitude, 6),
        "planets": draconic_points,
    }


def compute_western_aspects(planets: list[dict], orb: float = DEFAULT_ORB_DEGREES) -> list[dict]:
    """Detect Ptolemaic aspects between all pairs of planets.

    Args:
        planets: List of planet dictionaries (tropical) with ``name`` and
            ``longitude`` keys.
        orb: Maximum allowed deviation from the exact aspect angle, in degrees.

    Returns:
        List of detected aspects, sorted by the absolute orb.
    """
    aspects: list[dict] = []
    planet_list = [p for p in planets if p["name"] in PLANET_IDS]
    count = len(planet_list)

    for i in range(count):
        for j in range(i + 1, count):
            lon_a = float(planet_list[i]["longitude"])
            lon_b = float(planet_list[j]["longitude"])
            distance = min((lon_a - lon_b) % 360.0, (lon_b - lon_a) % 360.0)

            for aspect in ASPECT_DEFINITIONS:
                exact = float(aspect["angle"])
                variance = abs(distance - exact)
                if variance <= orb:
                    aspects.append(
                        {
                            "planet_1": planet_list[i]["name"],
                            "planet_2": planet_list[j]["name"],
                            "aspect": aspect["name"],
                            "orb_variance": round(variance, 3),
                        }
                    )
                    # A given pair can only match one aspect in this simple model.
                    break

    return sorted(aspects, key=lambda a: abs(a["orb_variance"]))


# Transit window bodies. Slow/karmic planets drive seismic change; fast planets
# (Sun, Moon, Mercury, Venus) are filtered out unless they form a strict
# conjunction to a natal luminary or angle.
_SLOW_TRANSIT_BODIES = ("Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "TrueNode")
_MARS_BODY = "Mars"
_FAST_TRANSIT_BODIES = ("Sun", "Moon", "Mercury", "Venus")

# Natal points that define a "Point of Impact". Aspects to outer planets are
# too frequent and noisy for a high-ticket executive report; we anchor windows
# to the angles and luminaries.
_PERSONAL_NATAL_BODIES = ("Sun", "Moon", "TrueNode", "Ascendant", "Midheaven")
_LUMINARY_ANGLE_BODIES = ("Sun", "Moon", "Ascendant")

# Major aspects used for transit-to-natal windows (ignore sextile to reduce noise).
_TRANSIT_WINDOW_ASPECTS = (
    (0.0, "Conjunction"),
    (90.0, "Square"),
    (120.0, "Trine"),
    (180.0, "Opposition"),
)

# Tight orb for transit hits: a pass is reported when the closest approach of
# the orb, refined to the minute, falls under it.
_TRANSIT_WINDOW_ORB = 1.5

# Days sampled beyond each end of the scan. A minimum of the orb is recognised
# only between two samples, so the extra days let the first and the last day
# of the window hold a hit, and keep hits outside the window out of it. Until
# 1.0.5 the scan clamped them instead: a hit still approaching on the last day
# got that day's date, one that peaked before the start got the start date.
_TRANSIT_SCAN_MARGIN_DAYS = 2

# Even tighter orb for fast-planet conjunctions to natal luminaries/angles;
# these are the only fast-planet events we surface.
_FAST_CONJUNCTION_ORB = 1.0


def _is_seismic_aspect(
    transit_body: str,
    natal_body: str,
    aspect_name: str,
    orb: float,
) -> bool:
    """Return True if a transit-to-natal aspect is worth reporting in M9.

    Filtering rules:
    - Slow/karmic bodies (Jupiter-Pluto + Nodes): report aspects to personal
      natal points (Sun, Moon, Node, Ascendant, MC).
    - Mars: report ingresses and conjunctions/oppositions to personal points.
      Squares/trines from Mars are too frequent for the 18-month executive view.
    - Fast bodies (Sun, Moon, Mercury, Venus): report ONLY strict conjunctions
      (orb < 1°) to natal Sun, Moon or Ascendant.
    """
    if natal_body not in _PERSONAL_NATAL_BODIES:
        return False

    if transit_body in _SLOW_TRANSIT_BODIES:
        return True

    if transit_body == _MARS_BODY:
        return aspect_name in ("Conjunction", "Opposition")

    if transit_body in _FAST_TRANSIT_BODIES:
        return aspect_name == "Conjunction" and orb < _FAST_CONJUNCTION_ORB

    return False


# Passes of a fast planet further apart than this are separate windows (the
# span of one retrograde loop). The Sun has no loop: every pass is its own.
# Slower bodies keep all passes of the scan in one window.
_PASS_LOOP_DAYS = {"Sun": 0.0, "Mercury": 60.0, "Venus": 120.0}


def _aspect_window(body: str, natal_name: str, aspect_name: str, passes: list[dict]) -> dict:
    """One transit-window entry from the passes of one geometric event."""
    passes = [{k: v for k, v in entry.items() if k != "jd"} for entry in passes]
    parts = [
        f"{entry['date']} (dokładnie)"
        if entry["exact"]
        else f"{entry['date']} (najbliżej, orb {entry['orb']}°, bez dokładnego przejścia)"
        for entry in passes
    ]
    return {
        "event_date": passes[0]["date"],
        "moment_utc": passes[0]["moment_utc"],
        "event_type": "aspect",
        "transit_body": body,
        "natal_body": natal_name,
        "aspect": aspect_name,
        "sign": passes[0]["sign"],
        "orb": min(entry["orb"] for entry in passes),
        "exact": any(entry["exact"] for entry in passes),
        "passes": passes,
        "description": (
            f"{body} {aspect_name.lower()} {natal_name} w {passes[0]['sign']}: "
            + "; ".join(parts) + "."
        ),
    }


def _score_window(window: dict) -> int:
    """Importance score for ranking windows when we need to cap the list."""
    body = window.get("transit_body", "")
    natal = window.get("natal_body")
    aspect = window.get("aspect")
    event_type = window.get("event_type")

    if event_type == "ingress":
        if body in _SLOW_TRANSIT_BODIES:
            return 7
        if body == _MARS_BODY:
            return 3
        return 1

    if natal in ("Sun", "Moon", "Ascendant", "Midheaven"):
        if body in _FAST_TRANSIT_BODIES:
            # Fast bodies are allowed only for strict conjunctions; keep them
            # below slow-body and Mars events so they don't drown the list.
            return 4 if aspect == "Conjunction" else 1
        if aspect == "Conjunction":
            return 10 if body in _SLOW_TRANSIT_BODIES else 6
        if aspect == "Opposition":
            return 8 if body in _SLOW_TRANSIT_BODIES else 5
        if aspect == "Square":
            return 7 if body in _SLOW_TRANSIT_BODIES else 3
        if aspect == "Trine":
            return 5 if body in _SLOW_TRANSIT_BODIES else 2

    if natal == "TrueNode":
        return 6 if aspect == "Conjunction" and body in _SLOW_TRANSIT_BODIES else 3

    return 2


def compute_transit_windows(
    natal_planets: list[dict],
    start_date: date,
    months: int = 18,
    natal_ascendant: dict | None = None,
    natal_midheaven: dict | None = None,
    max_windows: int = 20,
) -> list[dict]:
    """Find upcoming sign ingresses and exact transiting aspects for M9.

    Scans from ``start_date`` forward for the requested number of months.
    Returns a chronologically sorted list of high-impact windows/events for the
    ``Okna decyzyjne`` subsection. Slow/karmic planets drive the list; Mars is
    included for ingresses and conjunctions/oppositions to personal points;
    fast planets are included only for strict conjunctions to the natal Sun,
    Moon or Ascendant.

    Args:
        natal_planets: Natal tropical planet dictionaries (must include
            ``name`` and ``longitude``).
        start_date: Date from which to start scanning.
        months: How many months ahead to scan (default 18).
        natal_ascendant: Optional natal Ascendant dictionary.
        natal_midheaven: Optional natal Midheaven dictionary.
        max_windows: Hard cap on returned windows to avoid white-noise overload
            (default 20 for the executive report tier).

    Every geometric event is one window, and every time it happens inside the
    scan is one of its ``passes``: the moment of the closest approach, refined
    to the minute from a daily noon-UTC grid. A retrograde planet can make the
    same aspect three times; a planet that stations short of the degree makes
    a pass with ``exact: false`` and its minimum orb (Saturn stationing 0.84°
    from a natal MC never perfects the square). A sign ingress is one window
    per sign entered. The window's own ``event_date``/``moment_utc`` are its
    first pass, ``orb`` the smallest of them. The Sun, Mercury and Venus
    return to the same point a year on, which is a new window, not a pass
    (`_PASS_LOOP_DAYS`); the transiting Moon keeps only its first pass — it
    would otherwise repeat every month.

    Returns:
        List of transit window dictionaries with keys:
        ``event_date``, ``moment_utc``, ``event_type``, ``transit_body``,
        ``natal_body``, ``aspect``, ``sign``, ``orb``, ``exact``, ``passes``
        and ``description``.
    """
    natal_lookup: dict[str, dict] = {
        p["name"]: p
        for p in natal_planets
        if p.get("name") in PLANET_IDS
    }
    if natal_ascendant:
        natal_lookup[natal_ascendant["name"]] = natal_ascendant
    if natal_midheaven:
        natal_lookup[natal_midheaven["name"]] = natal_midheaven
    if not natal_lookup:
        return []

    end_date = start_date + timedelta(days=int(months * 30.4375))
    first_day = start_date - timedelta(days=_TRANSIT_SCAN_MARGIN_DAYS)
    sample_count = (end_date - first_day).days + _TRANSIT_SCAN_MARGIN_DAYS + 1
    grid = [julian_day_at_noon(first_day + timedelta(days=i)) for i in range(sample_count)]

    def inside(jd_ut: float) -> bool:
        return start_date <= jd_to_date(jd_ut) <= end_date

    bodies = [
        body
        for body in (*_SLOW_TRANSIT_BODIES, _MARS_BODY, *_FAST_TRANSIT_BODIES)
        if body in PLANET_IDS
    ]
    longitudes = {body: [tropical_longitude(jd, body) for jd in grid] for body in bodies}

    windows: list[dict] = []

    for body in bodies:
        if body not in (*_SLOW_TRANSIT_BODIES, _MARS_BODY):
            continue
        series = longitudes[body]
        crossings = [
            {
                "jd": bisect_change(
                    lambda t, body=body: sign_index(tropical_longitude(t, body)), grid[i - 1], grid[i]
                ),
                "from_sign": sign_of(series[i - 1]),
                "to_sign": sign_of(series[i]),
            }
            for i in range(1, len(grid))
            if sign_index(series[i]) != sign_index(series[i - 1])
        ]
        if body == "TrueNode":
            # A wobbling node can cross a sign boundary back and forth within
            # days: one ingress per burst, dated at its first crossing into
            # the sign it ends up in, none if it ends where it started.
            crossings = [
                next(c for c in group if c["to_sign"] == group[-1]["to_sign"]) | {
                    "from_sign": group[0]["from_sign"]
                }
                for group in cluster(crossings, NODE_CLUSTER_DAYS)
                if group[0]["from_sign"] != group[-1]["to_sign"]
            ]
        by_sign: dict[str, dict] = {}
        for crossing in crossings:
            moment = crossing["jd"]
            if not inside(moment):
                continue
            new_sign = crossing["to_sign"]
            entry = {
                "date": jd_to_date(moment).isoformat(),
                "moment_utc": jd_to_moment(moment),
                "from_sign": crossing["from_sign"],
                # The node's motion is retrograde by nature; saying so on
                # every node ingress would only confuse the reader.
                "retrograde": body != "TrueNode" and longitude_speed(moment, body) < 0.0,
            }
            window = by_sign.get(new_sign)
            if window is None:
                by_sign[new_sign] = {
                    "event_date": entry["date"],
                    "moment_utc": entry["moment_utc"],
                    "event_type": "ingress",
                    "transit_body": body,
                    "natal_body": None,
                    "aspect": None,
                    "sign": new_sign,
                    "orb": None,
                    "exact": None,
                    "passes": [entry],
                }
            else:
                window["passes"].append(entry)
        for window in by_sign.values():
            window["description"] = f"{body} wchodzi do {window['sign']}: " + "; ".join(
                f"{entry['date']} (z {entry['from_sign']}"
                + (", ruchem wstecznym)" if entry["retrograde"] else ")")
                for entry in window["passes"]
            ) + "."
            windows.append(window)

    for body in bodies:
        series = longitudes[body]
        # A minimum on the daily grid can sit up to one day's motion away from
        # the true one, so a sample that close to the orb is worth refining.
        motion = max(separation(series[i], series[i - 1]) for i in range(1, len(series)))
        # One window per retrograde loop: the Sun, Mercury and Venus come back
        # to the same point a year on, and that is a new event, not a pass.
        for natal_name, natal in natal_lookup.items():
            natal_lon = float(natal["longitude"])
            for angle, aspect_name in _TRANSIT_WINDOW_ASPECTS:
                if not _is_seismic_aspect(body, natal_name, aspect_name, 0.0):
                    continue

                def orb_at(t: float, body=body, natal_lon=natal_lon, angle=angle) -> float:
                    return aspect_orb(tropical_longitude(t, body), natal_lon, angle)

                orbs = [aspect_orb(lon, natal_lon, angle) for lon in series]
                passes: list[dict] = []
                for i in local_minima(orbs):
                    if orbs[i] - motion > _TRANSIT_WINDOW_ORB:
                        continue
                    moment, best = minimize(orb_at, grid[i - 1], grid[i + 1])
                    if best > _TRANSIT_WINDOW_ORB or not inside(moment):
                        continue
                    if not _is_seismic_aspect(body, natal_name, aspect_name, best):
                        continue
                    longitude = tropical_longitude(moment, body)
                    passes.append({
                        "jd": moment,
                        "date": jd_to_date(moment).isoformat(),
                        "moment_utc": jd_to_moment(moment),
                        "orb": round(best, 2),
                        "exact": best < EXACT_ORB,
                        "retrograde": longitude_speed(moment, body) < 0.0,
                        "sign": sign_of(longitude),
                    })
                if not passes:
                    continue
                if body == "TrueNode":
                    passes = merge_node_passes(passes)
                if body == "Moon":
                    passes = passes[:1]
                for group in cluster(passes, _PASS_LOOP_DAYS.get(body, float("inf"))):
                    windows.append(_aspect_window(body, natal_name, aspect_name, group))

    ranked = sorted(windows, key=lambda w: (_score_window(w), w["event_date"]), reverse=True)
    selected = ranked[:max_windows]
    return sorted(selected, key=lambda w: (w["event_date"], w["transit_body"]))


def _longitude_to_nakshatra(longitude: float) -> dict:
    """Map a sidereal longitude to a Nakshatra and Pada.

    The 360-degree zodiac is divided into 27 Nakshatras of 13°20' each.
    Each Nakshatra is further divided into 4 Padas of 3°20' each.

    Args:
        longitude: Sidereal ecliptic longitude in degrees [0, 360).

    Returns:
        Dictionary with nakshatra_number (1-27), nakshatra_name and pada (1-4).
    """
    normalized = longitude % 360.0
    nakshatra_index = int(normalized // NAKSHATRA_DEGREES) % NAKSHATRA_COUNT
    nakshatra_number = nakshatra_index + 1
    nakshatra_start = nakshatra_index * NAKSHATRA_DEGREES
    offset_in_nakshatra = normalized - nakshatra_start
    pada = int(offset_in_nakshatra // PADA_DEGREES) + 1

    # Clamp Pada to the valid 1-4 range as a defensive measure.
    pada = max(1, min(pada, PADA_COUNT))

    # Each pada is one navamsa (D9); the 108 of them run through the signs
    # from Aries, so pada 2 of Pushya is Virgo. Until 1.0.5 the model did this
    # itself and gave it as Taurus.
    navamsa_index = (nakshatra_index * PADA_COUNT + pada - 1) % SIGNS_COUNT

    return {
        "nakshatra_number": nakshatra_number,
        "nakshatra_name": NAKSHATRA_NAMES[nakshatra_index],
        "nakshatra_lord": VIMSHOTTARI_ORDER[nakshatra_index % 9],
        "pada": pada,
        "navamsa_sign": ZODIAC_SIGNS[navamsa_index],
    }


def _attach_nakshatras(planets: list[dict], ascendant: dict) -> list[dict]:
    """Attach Nakshatra, Pada and the Nakshatra's lord to every Vedic body.

    Args:
        planets: List of sidereal planet dictionaries.
        ascendant: Sidereal Ascendant dictionary.

    Returns:
        The planets in their usual order, then Ketu (opposite the true node),
        then the Ascendant — each with its Nakshatra data.
    """
    bodies = list(planets)
    node = next((p for p in planets if p["name"] == "TrueNode"), None)
    if node is not None:
        bodies.append(ketu_position(node))

    updated: list[dict] = []
    for body in bodies:
        entry = dict(body)
        if body["name"] in NAKSHATRA_BODIES:
            entry.update(_longitude_to_nakshatra(body["longitude"]))
        updated.append(entry)

    if ascendant["name"] in NAKSHATRA_BODIES:
        ascendant_with_nakshatra = dict(ascendant)
        ascendant_with_nakshatra.update(_longitude_to_nakshatra(ascendant["longitude"]))
        updated.append(ascendant_with_nakshatra)

    return updated


def compute_vedic_whole_sign_houses(ascendant_sign: str) -> list[dict]:
    """Build Whole Sign houses starting from the Ascendant's sign.

    In Whole Sign (Vedic) houses, the entire sign occupied by the Ascendant
    becomes the 1st house, the next sign the 2nd, and so on.

    Args:
        ascendant_sign: Name of the sidereal Ascendant sign.

    Returns:
        List of 12 Whole Sign house dictionaries.
    """
    try:
        start_index = ZODIAC_SIGNS.index(ascendant_sign)
    except ValueError as exc:
        raise ValueError(f"Unknown ascendant sign: {ascendant_sign}") from exc

    houses: list[dict] = []
    for house_number in range(1, 13):
        sign_index = (start_index + house_number - 1) % SIGNS_COUNT
        sign = ZODIAC_SIGNS[sign_index]
        houses.append(
            {
                "house_number": house_number,
                "longitude": round(sign_index * DEGREES_PER_SIGN, 6),
                "sign": sign,
                "degree_in_sign": 0.0,
            }
        )

    return houses


def compute_vedic_chart(
    jd_ut: float,
    latitude: float,
    longitude: float,
    birth_dt: "datetime | None" = None,
    reference_date: "date | None" = None,
) -> dict:
    """Calculate the complete Vedic (sidereal Lahiri) chart section.

    Args:
        jd_ut: Julian Day in Universal Time.
        latitude: Geographic latitude in decimal degrees.
        longitude: Geographic longitude in decimal degrees (positive east).
        birth_dt: Birth moment (UTC), required for the Vimshottari Dasha timeline.
        reference_date: Date at which the active Dasha is reported (defaults to today).

    Returns:
        Dictionary containing sidereal Ascendant, MC, Whole Sign houses,
        planets (with their houses from the Lagna and the Moon), Nakshatras,
        drishti, yogas, the panchanga, the applied ayanamsa value, the
        Vimshottari Dasha and Sade-Sati.
    """
    _apply_ayanamsa_mode()
    ayanamsa = round(float(swe.get_ayanamsa(jd_ut)), 6)

    # Whole Sign, not Placidus: the Vedic chart derives its houses from the
    # Ascendant's sign anyway, and Whole Sign is the only system defined beyond
    # the polar circles — so a birth in Tromso still gets a Jyotish chart.
    ascendant, midheaven, _ = compute_houses(
        jd_ut, latitude, longitude, sidereal=True, house_system="whole_sign"
    )
    sidereal_planets = compute_all_planets(jd_ut, sidereal=True)
    planets = attach_vedic_houses(sidereal_planets, ascendant)
    whole_sign_houses = compute_vedic_whole_sign_houses(ascendant["sign"])
    nakshatra_bodies = _attach_nakshatras(sidereal_planets, ascendant)

    moon_longitude = next(
        (p["longitude"] for p in planets if p["name"] == "Moon"), None
    )
    if moon_longitude is None:
        raise RuntimeError("Moon position missing; cannot compute Vimshottari Dasha")

    if birth_dt is None:
        raise ValueError("birth_dt is required to compute the Vimshottari Dasha")

    vimshottari_dasha = compute_vimshottari_dasha(
        moon_sidereal_longitude=moon_longitude,
        birth_dt=birth_dt,
        reference_date=reference_date,
    )

    moon_data = next(
        (p for p in planets if p["name"] == "Moon"), None
    )
    if moon_data is None:
        raise RuntimeError("Moon position missing; cannot compute Sade-Sati")

    sade_sati = compute_sade_sati(
        moon_sign=moon_data["sign"],
        reference_date=reference_date,
        birth_date=birth_dt.date(),
    )
    avakahada = compute_avakahada_chakra(
        nakshatra_name=vimshottari_dasha["moon_nakshatra"],
        moon_sign=moon_data["sign"],
    )

    return {
        "ayanamsa": ayanamsa,
        "system": "Lahiri (Chitra Paksha)",
        "ascendant": ascendant,
        "midheaven": midheaven,
        "houses": whole_sign_houses,
        "planets": planets,
        "nakshatras": nakshatra_bodies,
        "drishti": compute_drishti(planets, ascendant),
        "yogas": compute_yogas(planets, ascendant),
        "panchanga": compute_panchanga(jd_ut),
        "vimshottari_dasha": vimshottari_dasha,
        "sade_sati": sade_sati,
        "avakahada_chakra": avakahada,
    }
