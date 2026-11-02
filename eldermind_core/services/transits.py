"""Transit facts for the report timeline (M9): exact moments, aspects in force
on the reference day, and the Jupiter and Saturn returns.

Until 1.0.5 the report got only the 18-month windows, sampled once a day at
noon UTC, and the model worked out the rest itself. It got it wrong: "Jupiter
in 24° Leo approaching a trine to Uranus in 26° Aquarius" (an opposition),
"your Jupiter return is behind you" (Jupiter stations on the natal degree five
months later). Everything here is computed, so the prompt can forbid the model
to compute it.

All longitudes are tropical. Moments are UTC.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Callable

import swisseph as swe

from eldermind_core.core.config import PLANET_IDS, SIGNS_COUNT, ZODIAC_SIGNS

#: A local minimum of the orb below this is an exact hit. Refinement stops at
#: one minute of time, which leaves at most ~0.01° for the Moon; a station that
#: never reaches the degree stays above it.
EXACT_ORB = 0.05

#: Refinement tolerance, in days (one minute).
_TIME_TOLERANCE = 1.0 / 1440.0

#: Aspects of transiting planets to the natal chart in force on the reference
#: day (`compute_transit_aspects`).
TRANSIT_ASPECTS = (
    (0.0, "Conjunction"),
    (60.0, "Sextile"),
    (90.0, "Square"),
    (120.0, "Trine"),
    (180.0, "Opposition"),
)
TRANSIT_ASPECT_ORB = 3.0

#: Narrower orbs for the planets that cross 3° in a few days, so the list is
#: what is in force around the day, not the whole week.
_FAST_ASPECT_ORBS = {"Sun": 1.0, "Mercury": 1.0, "Venus": 1.0, "Mars": 2.0}

#: The Moon changes aspect within hours; on a reference *day* it is noise.
_TRANSIT_ASPECT_BODIES = tuple(name for name in PLANET_IDS if name != "Moon")

#: The true node wobbles about a degree either way every couple of weeks, so
#: near a natal point it makes a burst of minima a fortnight apart. They are
#: one event: minima of the node closer than this are merged, and a search for
#: its closest approach keeps going until the orb is this much past the best.
NODE_CLUSTER_DAYS = 30.0
_NODE_SETTLE_ORB = 2.0
_MEAN_NODE_DAILY_MOTION = 0.0529539

#: How far ahead or back to look for the closest approach of an aspect in
#: force today. Pluto, the slowest, crosses a 3° orb in well under 400 days.
_CLOSEST_SEARCH_DAYS = 400

#: Orbital period in years, and the sampling step in days for the return scan.
RETURN_BODIES = {"Jupiter": (11.862, 2.0), "Saturn": (29.457, 3.0)}

#: A return pass is a local minimum of the distance to the natal degree within
#: this orb; a station counts toward the return when it falls this close.
_RETURN_ORB = 3.0
_RETURN_STATION_ORB = 8.0

#: Passes further apart than this belong to different returns.
_RETURN_EPISODE_GAP_DAYS = 400


def tropical_longitude(jd_ut: float, body: str) -> float:
    """Tropical longitude of a body, in degrees [0, 360)."""
    result, _ = swe.calc_ut(jd_ut, PLANET_IDS[body], 0)
    return float(result[0]) % 360.0


def longitude_speed(jd_ut: float, body: str) -> float:
    """Daily motion in longitude, negative when retrograde."""
    result, _ = swe.calc_ut(jd_ut, PLANET_IDS[body], swe.FLG_SPEED)
    return float(result[3])


def separation(lon_a: float, lon_b: float) -> float:
    """Angular distance between two longitudes, in [0, 180]."""
    return abs((lon_a - lon_b + 180.0) % 360.0 - 180.0)


def aspect_orb(lon_a: float, lon_b: float, angle: float) -> float:
    return abs(separation(lon_a, lon_b) - angle)


def sign_index(longitude: float) -> int:
    return int((longitude % 360.0) // 30.0) % SIGNS_COUNT


def sign_of(longitude: float) -> str:
    return ZODIAC_SIGNS[sign_index(longitude)]


def jd_to_datetime(jd_ut: float) -> datetime:
    year, month, day, hours = swe.revjul(jd_ut)
    moment = datetime(year, month, day, tzinfo=timezone.utc) + timedelta(hours=hours)
    # Round to the minute: refinement is no finer, and seconds only add noise.
    return (moment + timedelta(seconds=30)).replace(second=0, microsecond=0)


def jd_to_date(jd_ut: float) -> date:
    return jd_to_datetime(jd_ut).date()


def jd_to_moment(jd_ut: float) -> str:
    """ISO 8601 UTC moment to the minute, e.g. ``2028-04-29T01:12Z``."""
    return jd_to_datetime(jd_ut).strftime("%Y-%m-%dT%H:%MZ")


def julian_day_at_noon(day: date) -> float:
    return swe.julday(day.year, day.month, day.day, 12.0)


def minimize(f: Callable[[float], float], low: float, high: float) -> tuple[float, float]:
    """Golden-section search: the minimum of a unimodal `f` on [low, high].

    Returns ``(x, f(x))``. Used on two-day brackets around a daily-grid
    minimum, where the orb is a single V (a crossing) or a single U (a
    station).
    """
    ratio = 0.6180339887498949
    a, b = low, high
    c = b - ratio * (b - a)
    d = a + ratio * (b - a)
    fc, fd = f(c), f(d)
    while b - a > _TIME_TOLERANCE:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - ratio * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + ratio * (b - a)
            fd = f(d)
    x = (a + b) / 2.0
    return x, f(x)


def bisect_change(f: Callable[[float], object], low: float, high: float) -> float:
    """The moment on [low, high] where `f` stops returning `f(low)`."""
    before = f(low)
    a, b = low, high
    while b - a > _TIME_TOLERANCE:
        middle = (a + b) / 2.0
        if f(middle) == before:
            a = middle
        else:
            b = middle
    return (a + b) / 2.0


def local_minima(values: list[float]) -> list[int]:
    """Indices of interior local minima of a sampled series.

    `<=` on the left and `<` on the right, so a two-sample plateau counts
    once. The end samples are never minima: a scan that wants to judge its
    first and last day has to sample one step beyond them.
    """
    return [
        i
        for i in range(1, len(values) - 1)
        if values[i] <= values[i - 1] and values[i] < values[i + 1]
    ]


def _stations(body: str, jd_from: float, jd_to: float, step: float) -> list[tuple[float, str]]:
    """Moments the body turns retrograde or direct between two dates."""
    found: list[tuple[float, str]] = []
    jd = jd_from
    previous = longitude_speed(jd, body) < 0.0
    while jd < jd_to:
        following = min(jd + step, jd_to)
        retrograde = longitude_speed(following, body) < 0.0
        if retrograde != previous:
            moment = bisect_change(lambda t: longitude_speed(t, body) < 0.0, jd, following)
            found.append((moment, "retrograde" if retrograde else "direct"))
        previous = retrograde
        jd = following
    return found


def _natal_points(
    natal_planets: list[dict],
    natal_ascendant: dict | None,
    natal_midheaven: dict | None,
) -> list[tuple[str, float]]:
    points = [
        (planet["name"], float(planet["longitude"]))
        for planet in natal_planets
        if planet.get("name") in PLANET_IDS
    ]
    for angle in (natal_ascendant, natal_midheaven):
        if angle:
            points.append((angle["name"], float(angle["longitude"])))
    return points


def cluster(items: list[dict], gap_days: float) -> list[list[dict]]:
    """Split time-ordered items (each with ``jd``) where they are `gap_days` apart."""
    groups: list[list[dict]] = []
    for item in items:
        if groups and item["jd"] - groups[-1][-1]["jd"] <= gap_days:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def merge_node_passes(passes: list[dict]) -> list[dict]:
    """One pass per burst of true-node minima: the first exact one, else the closest."""
    merged = []
    for group in cluster(passes, NODE_CLUSTER_DAYS):
        exact = [entry for entry in group if entry["exact"]]
        merged.append(exact[0] if exact else min(group, key=lambda entry: entry["orb"]))
    return merged


def _closest_approach(
    body: str, natal_lon: float, angle: float, jd_ut: float, direction: int
) -> dict | None:
    """The next (direction=+1) or previous (-1) minimum of the orb."""
    def orb(t: float) -> float:
        return aspect_orb(tropical_longitude(t, body), natal_lon, angle)

    settle = _NODE_SETTLE_ORB if body == "TrueNode" else 0.0
    best_jd, best_orb = jd_ut, orb(jd_ut)
    for day in range(1, _CLOSEST_SEARCH_DAYS + 1):
        jd = jd_ut + direction * day
        value = orb(jd)
        if value < best_orb:
            best_jd, best_orb = jd, value
        elif value > best_orb + settle:
            moment, best = minimize(orb, best_jd - 1.0, best_jd + 1.0)
            return {
                "date": jd_to_date(moment).isoformat(),
                "moment_utc": jd_to_moment(moment),
                "orb": round(best, 2),
                "exact": best < EXACT_ORB,
            }
    return None


def compute_transit_aspects(
    natal_planets: list[dict],
    jd_ut: float,
    natal_ascendant: dict | None = None,
    natal_midheaven: dict | None = None,
    orb: float = TRANSIT_ASPECT_ORB,
) -> list[dict]:
    """Aspects of the transiting planets to the natal chart at one moment.

    Every transiting body except the Moon against every natal planet, the
    Ascendant and the Midheaven, the five Ptolemaic aspects within `orb`
    (narrower for the Sun, Mercury, Venus and Mars).
    Each entry says whether the aspect is applying (the orb shrinks) and when
    it is or was closest: the next minimum of the orb for an applying aspect,
    the previous one for a separating one, with ``exact: false`` when the
    planet stations short of the degree.
    """
    points = _natal_points(natal_planets, natal_ascendant, natal_midheaven)
    found: list[dict] = []
    for body in _TRANSIT_ASPECT_BODIES:
        now = tropical_longitude(jd_ut, body)
        if body == "TrueNode":
            # Applying by the node's mean motion, not by today's wobble.
            later = now - _MEAN_NODE_DAILY_MOTION
        else:
            later = tropical_longitude(jd_ut + 1.0 / 24.0, body)
        retrograde = longitude_speed(jd_ut, body) < 0.0
        limit = min(orb, _FAST_ASPECT_ORBS.get(body, orb))
        for natal_name, natal_lon in points:
            for angle, aspect_name in TRANSIT_ASPECTS:
                current = aspect_orb(now, natal_lon, angle)
                if current > limit:
                    continue
                applying = aspect_orb(later, natal_lon, angle) < current
                found.append({
                    "transit_body": body,
                    "transit_sign": sign_of(now),
                    "transit_degree": int(now % 30.0),
                    "transit_retrograde": retrograde,
                    "natal_body": natal_name,
                    "natal_sign": sign_of(natal_lon),
                    "natal_degree": int(natal_lon % 30.0),
                    "aspect": aspect_name,
                    "orb": round(current, 2),
                    "applying": applying,
                    "closest": _closest_approach(
                        body, natal_lon, angle, jd_ut, 1 if applying else -1
                    ),
                })
    return sorted(found, key=lambda entry: entry["orb"])


def _return_passes(body: str, natal_lon: float, jd_from: float, jd_to: float, step: float) -> list[dict]:
    def orb(t: float) -> float:
        return separation(tropical_longitude(t, body), natal_lon)

    grid = [jd_from + i * step for i in range(int((jd_to - jd_from) / step) + 1)]
    values = [orb(jd) for jd in grid]
    passes: list[dict] = []
    for i in local_minima(values):
        if values[i] > _RETURN_ORB + step:
            continue
        moment, best = minimize(orb, grid[i - 1], grid[i + 1])
        if best > _RETURN_ORB:
            continue
        passes.append({
            "jd": moment,
            "date": jd_to_date(moment).isoformat(),
            "moment_utc": jd_to_moment(moment),
            "orb": round(best, 2),
            "exact": best < EXACT_ORB,
            "retrograde": longitude_speed(moment, body) < 0.0,
        })
    return passes


def compute_planet_returns(
    natal_planets: list[dict],
    jd_ut: float,
    birth_jd_ut: float | None = None,
    bodies: tuple[str, ...] = tuple(RETURN_BODIES),
) -> list[dict]:
    """The Jupiter and Saturn returns nearest to a moment.

    For each body: every pass over the natal degree (exact, or the closest
    approach when the planet stations short of it), the stations of that
    return, and its status relative to `jd_ut` — ``past``, ``in_progress``
    (between the first and the last pass) or ``upcoming``. With the birth
    moment, also which return in life it is.
    """
    natal = {planet["name"]: float(planet["longitude"]) for planet in natal_planets}
    returns: list[dict] = []
    for body in bodies:
        if body not in natal:
            continue
        period_years, step = RETURN_BODIES[body]
        half_period = period_years * 365.25 / 2.0
        natal_lon = natal[body]
        passes = _return_passes(body, natal_lon, jd_ut - half_period, jd_ut + half_period, step)
        if not passes:
            continue

        episodes: list[list[dict]] = [[passes[0]]]
        for entry in passes[1:]:
            if entry["jd"] - episodes[-1][-1]["jd"] > _RETURN_EPISODE_GAP_DAYS:
                episodes.append([entry])
            else:
                episodes[-1].append(entry)

        def distance(episode: list[dict]) -> float:
            first, last = episode[0]["jd"], episode[-1]["jd"]
            return 0.0 if first <= jd_ut <= last else min(abs(first - jd_ut), abs(last - jd_ut))

        episode = min(episodes, key=distance)
        first, last = episode[0]["jd"], episode[-1]["jd"]
        if last < jd_ut:
            status = "past"
        elif first > jd_ut:
            status = "upcoming"
        else:
            status = "in_progress"

        stations = []
        for moment, kind in _stations(body, first - 200.0, last + 200.0, step):
            longitude = tropical_longitude(moment, body)
            to_natal = separation(longitude, natal_lon)
            if to_natal > _RETURN_STATION_ORB:
                continue
            stations.append({
                "date": jd_to_date(moment).isoformat(),
                "moment_utc": jd_to_moment(moment),
                "kind": kind,
                "sign": sign_of(longitude),
                "degree": int(longitude % 30.0),
                "orb_to_natal": round(to_natal, 2),
            })

        entry: dict = {
            "body": body,
            "natal_sign": sign_of(natal_lon),
            "natal_degree": int(natal_lon % 30.0),
            "status": status,
            "passes": [{k: v for k, v in p.items() if k != "jd"} for p in episode],
            "stations": stations,
        }
        if birth_jd_ut is not None:
            midpoint = (first + last) / 2.0
            entry["return_number"] = max(
                1, round((midpoint - birth_jd_ut) / (period_years * 365.25))
            )
            entry["age_at_first_pass"] = int((first - birth_jd_ut) / 365.25)
        returns.append(entry)
    return returns


__all__ = [
    "EXACT_ORB",
    "TRANSIT_ASPECTS",
    "TRANSIT_ASPECT_ORB",
    "aspect_orb",
    "NODE_CLUSTER_DAYS",
    "bisect_change",
    "cluster",
    "compute_planet_returns",
    "compute_transit_aspects",
    "jd_to_date",
    "jd_to_moment",
    "julian_day_at_noon",
    "local_minima",
    "longitude_speed",
    "merge_node_passes",
    "minimize",
    "separation",
    "sign_index",
    "sign_of",
    "tropical_longitude",
]
