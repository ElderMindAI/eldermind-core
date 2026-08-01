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
from eldermind_core.services.vedic_dasha import compute_avakahada_chakra, compute_vimshottari_dasha
from eldermind_core.services.sade_sati import compute_sade_sati


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


def compute_draconic_chart(jd_ut: float) -> dict:
    """Calculate the Draconic chart by shifting the tropical zodiac to the
    True North Node.

    In the Draconic system 0° Aries is aligned with the tropical longitude of
    the North Node. For every planet/point we subtract the Node's longitude and
    wrap to [0, 360).

    The output rounds positional data to whole degrees so prompts never contain
    misleading ``X°YY'`` values where YY > 59 (e.g. 8°91').

    Args:
        jd_ut: Julian Day in Universal Time.

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
        draconic_points.append(
            {
                "name": name,
                "draconic_longitude": round(draconic_longitude, 6),
                "sign": sign,
                # Round to whole degrees to prevent LLM hallucinations like 8°91'.
                "degree_in_sign": int(round(degree_in_sign)) % 30,
                "tropical_longitude": round(tropical["longitude"], 6),
            }
        )

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

# Tight orb for "exact" transit hits; we report the day of minimum orb within range.
_TRANSIT_WINDOW_ORB = 1.5

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

    Returns:
        List of transit window dictionaries with keys:
        ``event_date``, ``event_type``, ``transit_body``, ``natal_body``,
        ``aspect``, ``sign``, ``orb`` and ``description``.
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
    current = start_date

    windows: list[dict] = []
    last_sign: dict[str, str] = {}

    # Use noon UTC for the daily sample; accurate enough for month-level windows.
    while current <= end_date:
        jd_ut = _utc_to_julian_day_ut(datetime.combine(current, time(12, 0), tzinfo=ZoneInfo("UTC")))

        for body in (*_SLOW_TRANSIT_BODIES, _MARS_BODY, *_FAST_TRANSIT_BODIES):
            if body not in PLANET_IDS:
                continue
            transit_pos = compute_planet_position(jd_ut, body, PLANET_IDS[body])

            # Ingress detection (always keep ingresses of slow bodies and Mars).
            prev_sign = last_sign.get(body)
            if prev_sign is not None and transit_pos["sign"] != prev_sign:
                if body in (*_SLOW_TRANSIT_BODIES, _MARS_BODY):
                    windows.append({
                        "event_date": current.isoformat(),
                        "event_type": "ingress",
                        "transit_body": body,
                        "natal_body": None,
                        "aspect": None,
                        "sign": transit_pos["sign"],
                        "orb": None,
                        "description": (
                            f"{body} przechodzi z {prev_sign} do {transit_pos['sign']} "
                            f"(ok. {current.isoformat()})."
                        ),
                    })
            last_sign[body] = transit_pos["sign"]

            # Exact aspect detection (tight orb) to natal planets.
            transit_lon = transit_pos["longitude"]
            for natal_name, natal in natal_lookup.items():
                natal_lon = natal["longitude"]
                for angle, aspect_name in _TRANSIT_WINDOW_ASPECTS:
                    distance = min(
                        (transit_lon - natal_lon) % 360.0,
                        (natal_lon - transit_lon) % 360.0,
                    )
                    variance = abs(distance - angle)
                    if variance <= _TRANSIT_WINDOW_ORB:
                        if not _is_seismic_aspect(body, natal_name, aspect_name, variance):
                            continue
                        windows.append({
                            "event_date": current.isoformat(),
                            "event_type": "aspect",
                            "transit_body": body,
                            "natal_body": natal_name,
                            "aspect": aspect_name,
                            "sign": transit_pos["sign"],
                            "orb": round(variance, 2),
                            "description": (
                                f"{body} {aspect_name.lower()} {natal_name} "
                                f"w {transit_pos['sign']} (ok. {current.isoformat()}, "
                                f"orb {round(variance, 1)}°)."
                            ),
                        })

        current += timedelta(days=1)

    # Deduplicate contiguous duplicate (body, natal, aspect) hits by keeping
    # the single day with the smallest orb for each geometric event.
    grouped: dict[tuple[str, str | None, str | None, str], dict] = {}
    for window in windows:
        key = (
            window["transit_body"],
            window.get("natal_body"),
            window.get("aspect"),
            window.get("event_type"),
        )
        existing = grouped.get(key)
        if existing is None or (window.get("orb") is not None and (
            existing.get("orb") is None or window["orb"] < existing["orb"]
        )):
            grouped[key] = window

    ranked = sorted(grouped.values(), key=lambda w: (_score_window(w), w["event_date"]), reverse=True)
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

    return {
        "nakshatra_number": nakshatra_number,
        "nakshatra_name": NAKSHATRA_NAMES[nakshatra_index],
        "pada": pada,
    }


def _attach_nakshatras(planets: list[dict], ascendant: dict) -> list[dict]:
    """Attach Nakshatra/Pada data to Sun, Moon and Ascendant in the Vedic section.

    Args:
        planets: List of sidereal planet dictionaries.
        ascendant: Sidereal Ascendant dictionary.

    Returns:
        Updated list of planet dictionaries including Nakshatra data where applicable.
    """
    updated: list[dict] = []
    for body in planets:
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
        planets, the applied ayanamsa value and the Vimshottari Dasha.
    """
    _apply_ayanamsa_mode()
    ayanamsa = round(float(swe.get_ayanamsa(jd_ut)), 6)

    # Whole Sign, not Placidus: the Vedic chart derives its houses from the
    # Ascendant's sign anyway, and Whole Sign is the only system defined beyond
    # the polar circles — so a birth in Tromso still gets a Jyotish chart.
    ascendant, midheaven, _ = compute_houses(
        jd_ut, latitude, longitude, sidereal=True, house_system="whole_sign"
    )
    planets = compute_all_planets(jd_ut, sidereal=True)
    whole_sign_houses = compute_vedic_whole_sign_houses(ascendant["sign"])
    nakshatra_bodies = _attach_nakshatras(planets, ascendant)

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
    )
    avakahada = compute_avakahada_chakra(
        nakshatra_name=vimshottari_dasha["moon_nakshatra"]
    )

    return {
        "ayanamsa": ayanamsa,
        "system": "Lahiri (Chitra Paksha)",
        "ascendant": ascendant,
        "midheaven": midheaven,
        "houses": whole_sign_houses,
        "planets": planets,
        "nakshatras": nakshatra_bodies,
        "vimshottari_dasha": vimshottari_dasha,
        "sade_sati": sade_sati,
        "avakahada_chakra": avakahada,
    }
