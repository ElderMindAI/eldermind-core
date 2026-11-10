"""A calendar year as spans: transit windows from-to, house stays, retrograde
periods, eclipses, personal months and the BaZi months.

`compute_transit_windows` gives the moment of every exact pass, which is what
the report timeline (M9) needs. A calendar needs the span around it: the day
the transiting body comes within the orb of the natal point and the day it
leaves. A retrograde planet leaves and comes back, so one window can have
several segments; a span that began before the year keeps its real start.

A natal point is given as a longitude with a half-width. With an exact birth
time the half-width is 0. Without one the caller passes the arc the point
covers during the whole birth day (`point_range`): the orb is then measured
to the nearest point of that arc, so a span is the widest the day allows and
"exact" becomes a range of dates instead of one moment. Nothing here assumes
a time of day.

All longitudes are tropical. Moments are UTC to the minute; dates are local
to the `tz` the caller names.
"""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import swisseph as swe

from eldermind_core.services import bazi as _bazi
from eldermind_core.services.ephemeris import _which_house
from eldermind_core.services.numerology import _digit_sum, compute_personal_year
from eldermind_core.services.transits import (
    EXACT_ORB,
    NODE_CLUSTER_DAYS,
    _stations,
    aspect_orb,
    bisect_change,
    jd_to_datetime,
    jd_to_moment,
    julian_day_at_noon,
    local_minima,
    longitude_speed,
    minimize,
    separation,
    sign_of,
    tropical_longitude,
)

#: The orb a span is measured in: the same 1.5° that `compute_transit_windows`
#: uses to find a pass, so every window here contains the passes listed there.
#: Mars crosses 1.5° in two days; 1° keeps its windows to the days around it.
SPAN_ORBS = {
    "Jupiter": 1.5,
    "Saturn": 1.5,
    "Uranus": 1.5,
    "Neptune": 1.5,
    "Pluto": 1.5,
    "TrueNode": 1.5,
    "Mars": 1.0,
    "Sun": 1.0,
    "Mercury": 1.0,
    "Venus": 1.0,
}
SLOW_BODIES = ("Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "TrueNode")
#: As in M9: the fast planets count only in conjunction with the natal Sun,
#: Moon or Ascendant, the days a calendar can name in one line.
FAST_BODIES = ("Sun", "Mercury", "Venus")
_FAST_TARGETS = ("Sun", "Moon", "Ascendant")
SPAN_ASPECTS = ((0.0, "Conjunction"), (90.0, "Square"), (120.0, "Trine"), (180.0, "Opposition"))
#: Mars squares and trines come every few weeks; as in M9 only these count.
MARS_ASPECTS = ("Conjunction", "Opposition")
NATAL_TARGETS = ("Sun", "Moon", "TrueNode", "Ascendant", "Midheaven")

#: Segments of one event closer than this are one window (one retrograde
#: loop). Mars loops in about 80 days; the slow planets in under a year. The
#: Sun comes back a year on, which is a new window (M9's `_PASS_LOOP_DAYS`).
_LOOP_GAP_DAYS = {"Mars": 120.0, "Sun": 0.0, "Mercury": 60.0, "Venus": 120.0}
_DEFAULT_LOOP_GAP_DAYS = 400.0

#: Pluto can stay within 1.5° of a point for about two years, so the scan
#: reaches this far beyond each end of the year to find the real start and end.
_SCAN_MARGIN_DAYS = 1100

#: Bodies whose stay in a natal house is a period worth a calendar line.
HOUSE_BODIES = ("Jupiter", "Saturn")
_HOUSE_MARGIN_DAYS = 1200

RETROGRADE_BODIES = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")

#: An eclipse counts for a natal point within this orb of a conjunction or an
#: opposition, the widest orb in common use for eclipses.
ECLIPSE_ORB = 3.0

#: Branch pairs that clash (liu chong), each one six branches apart.
BRANCH_CLASHES = {
    "子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
    "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}
_BRANCHES = list(_bazi.ZODIAC_ANIMALS.keys())  # 子 first


# --------------------------------------------------------------------- points

def natal_point(name: str, longitude: float, half_width: float = 0.0) -> dict:
    """A natal target: centre longitude and the half-width of the arc around it."""
    return {"name": name, "longitude": float(longitude) % 360.0, "half_width": float(half_width)}


def point_range(name: str, longitudes: list[float]) -> dict:
    """The smallest arc holding every longitude a point takes during the birth day.

    The samples come in time order, and a body moves less than 180° in a day,
    so the arc from the first sample through the others is the one it swept.
    """
    first = float(longitudes[0])
    offsets = [((float(lon) - first + 180.0) % 360.0) - 180.0 for lon in longitudes]
    low, high = min(offsets), max(offsets)
    centre = (first + (low + high) / 2.0) % 360.0
    return natal_point(name, centre, (high - low) / 2.0)


def _orb_to(point: dict, longitude: float, angle: float) -> float:
    """Orb of the aspect to the nearest longitude of the point's arc."""
    return max(0.0, aspect_orb(longitude, point["longitude"], angle) - point["half_width"])


# ---------------------------------------------------------------------- dates

def _local_date(jd_ut: float, tz: ZoneInfo) -> date:
    return jd_to_datetime(jd_ut).astimezone(tz).date()


def _stamp(jd_ut: float, tz: ZoneInfo) -> dict:
    return {"date": _local_date(jd_ut, tz).isoformat(), "moment_utc": jd_to_moment(jd_ut)}


def _grid(first: date, last: date) -> list[float]:
    return [julian_day_at_noon(first + timedelta(days=i)) for i in range((last - first).days + 1)]


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    """(first, last) index of every run of True."""
    runs, start = [], None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(flags) - 1))
    return runs


def _group(items: list[dict], gap_days: float) -> list[list[dict]]:
    """Split time-ordered items (``start_jd``/``end_jd``) where the gap exceeds `gap_days`."""
    groups: list[list[dict]] = []
    for item in items:
        if groups and item["start_jd"] - groups[-1][-1]["end_jd"] <= gap_days:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


# -------------------------------------------------------------- aspect spans

def _exact_range(orb, peak: float, grid: list[float], orbs: list[float], i: int) -> tuple[float, float]:
    """The stretch around `peak` where the aspect is exact to some point of the arc.

    A slow planet can sit inside the arc for days, so the bracket is widened
    to the nearest samples outside it before bisecting.
    """
    def inside(t: float) -> bool:
        return orb(t) < EXACT_ORB

    left, right = i - 1, i + 1
    while left > 0 and orbs[left] < EXACT_ORB:
        left -= 1
    while right < len(grid) - 1 and orbs[right] < EXACT_ORB:
        right += 1
    return bisect_change(inside, peak, grid[left]), bisect_change(inside, peak, grid[right])


def _aspect_windows_for(
    body: str,
    point: dict,
    angle: float,
    aspect: str,
    grid: list[float],
    series: list[float],
    year: tuple[date, date],
    tz: ZoneInfo,
    house_cusps: list[dict] | None,
) -> list[dict]:
    limit = SPAN_ORBS[body]

    def orb(t: float) -> float:
        return _orb_to(point, tropical_longitude(t, body), angle)

    orbs = [_orb_to(point, lon, angle) for lon in series]
    minima = local_minima(orbs)
    segments: list[dict] = []
    for first, last in _runs([value <= limit for value in orbs]):
        if first == 0 or last == len(grid) - 1:
            continue  # cut by the scan: the margin is meant to make this impossible
        start = bisect_change(lambda t: orb(t) <= limit, grid[first - 1], grid[first])
        end = bisect_change(lambda t: orb(t) <= limit, grid[last], grid[last + 1])
        passes = []
        for i in (m for m in minima if first - 1 <= m <= last + 1):
            moment, best = minimize(orb, grid[i - 1], grid[i + 1])
            if best > limit:
                continue
            longitude = tropical_longitude(moment, body)
            entry = {
                **_stamp(moment, tz),
                "jd": moment,
                "orb": round(best, 2),
                "exact": best < EXACT_ORB,
                "retrograde": longitude_speed(moment, body) < 0.0,
                "sign": sign_of(longitude),
            }
            if point["half_width"] > 0 and entry["exact"]:
                low, high = _exact_range(orb, moment, grid, orbs, i)
                entry["exact_from"] = _local_date(low, tz).isoformat()
                entry["exact_to"] = _local_date(high, tz).isoformat()
            if house_cusps:
                entry["natal_house"] = _which_house(longitude, house_cusps)
            previous = passes[-1] if passes else None
            if previous and "exact_from" in entry and "exact_to" in previous and entry["exact_from"] <= previous["exact_to"]:
                # Two minima inside one stretch of exactness (a station on the
                # arc): one pass, the stretch running to the later end.
                previous["exact_to"] = max(previous["exact_to"], entry["exact_to"])
                continue
            passes.append(entry)
        segments.append({"start_jd": start, "end_jd": end, "passes": passes})

    if body == "TrueNode":
        # The wobbling node slips out of the orb and back within days; that
        # is one stay, not several.
        merged: list[dict] = []
        for group in _group(segments, NODE_CLUSTER_DAYS):
            merged.append({
                "start_jd": group[0]["start_jd"],
                "end_jd": group[-1]["end_jd"],
                "passes": [p for seg in group for p in seg["passes"]],
            })
        segments = merged

    windows = []
    for group in _group(segments, _LOOP_GAP_DAYS.get(body, _DEFAULT_LOOP_GAP_DAYS)):
        start_jd, end_jd = group[0]["start_jd"], group[-1]["end_jd"]
        start_day, end_day = _local_date(start_jd, tz), _local_date(end_jd, tz)
        if end_day < year[0] or start_day > year[1]:
            continue
        passes = [p for seg in group for p in seg["passes"]]
        if body == "TrueNode" and passes:
            passes = _one_node_pass_per_burst(passes)
        window = {
            "kind": "aspect",
            "body": body,
            "target": point["name"],
            "aspect": aspect,
            "start": start_day.isoformat(),
            "end": end_day.isoformat(),
            "start_utc": jd_to_moment(start_jd),
            "end_utc": jd_to_moment(end_jd),
            "starts_before_year": start_day < year[0],
            "ends_after_year": end_day > year[1],
            "segments": [
                {"start": _local_date(s["start_jd"], tz).isoformat(), "end": _local_date(s["end_jd"], tz).isoformat()}
                for s in group
            ],
            "passes": [{k: v for k, v in p.items() if k != "jd"} for p in passes],
            "exact": any(p["exact"] for p in passes),
            "min_orb": min((p["orb"] for p in passes), default=None),
        }
        in_year = [p for p in passes if year[0].isoformat() <= p["date"] <= year[1].isoformat()]
        reference = (in_year or passes or [None])[0]
        if reference and "natal_house" in reference:
            window["natal_house"] = reference["natal_house"]
        window["score"] = score_window(window)
        windows.append(window)
    return windows


def _one_node_pass_per_burst(passes: list[dict]) -> list[dict]:
    """One pass per burst of node minima: the first exact one, else the closest."""
    kept: list[dict] = []
    for item in passes:
        if kept and item["jd"] - kept[-1]["jd"] <= NODE_CLUSTER_DAYS:
            previous = kept[-1]
            if not previous["exact"] and (item["exact"] or item["orb"] < previous["orb"]):
                kept[-1] = item
            continue
        kept.append(item)
    return kept


def score_window(window: dict) -> int:
    """Importance for choosing the main windows; the same order as M9's ranking."""
    body, target, aspect = window["body"], window["target"], window["aspect"]
    if body in FAST_BODIES:
        return 4
    if target == "TrueNode":
        return 6 if aspect == "Conjunction" and body in SLOW_BODIES else 3
    slow = body in SLOW_BODIES
    return {
        "Conjunction": 10 if slow else 6,
        "Opposition": 8 if slow else 5,
        "Square": 7 if slow else 3,
        "Trine": 5 if slow else 2,
    }[aspect]


def aspect_spans(
    points: list[dict],
    year: int,
    tz: str = "Europe/Warsaw",
    *,
    bodies: tuple[str, ...] = (*SLOW_BODIES, "Mars"),
    house_cusps: list[dict] | None = None,
) -> list[dict]:
    """Every window of a transiting body in orb of a natal point during `year`.

    Each window has ``start``/``end`` (local dates; earlier or later than the
    year when the span crosses its edge, flagged by ``starts_before_year`` and
    ``ends_after_year``), its ``segments`` (one per stay in the orb), its
    ``passes`` (closest approaches, refined to the minute) and a ``score``.
    Sorted by start.
    """
    zone = ZoneInfo(tz)
    bounds = (date(year, 1, 1), date(year, 12, 31))
    margin = _SCAN_MARGIN_DAYS if set(bodies) - set(FAST_BODIES) - {"Mars"} else 200
    grid = _grid(bounds[0] - timedelta(days=margin), bounds[1] + timedelta(days=margin))
    targets = [p for p in points if p["name"] in NATAL_TARGETS]
    windows: list[dict] = []
    for body in bodies:
        series = [tropical_longitude(jd, body) for jd in grid]
        for point in targets:
            for angle, aspect in SPAN_ASPECTS:
                if body == "Mars" and aspect not in MARS_ASPECTS:
                    continue
                if body in FAST_BODIES and (aspect != "Conjunction" or point["name"] not in _FAST_TARGETS):
                    continue
                windows.extend(
                    _aspect_windows_for(body, point, angle, aspect, grid, series, bounds, zone, house_cusps)
                )
    windows.sort(key=lambda w: (w["start"], w["body"], w["target"]))
    seen: dict[str, int] = {}
    for window in windows:
        key = f"{window['body']}-{window['aspect']}-{window['target']}".lower()
        seen[key] = seen.get(key, 0) + 1
        window["id"] = f"{key}-{seen[key]}"
    return windows


# --------------------------------------------------------------- house stays

def house_periods(
    house_cusps: list[dict],
    year: int,
    tz: str = "Europe/Warsaw",
    bodies: tuple[str, ...] = HOUSE_BODIES,
) -> list[dict]:
    """Stays of Jupiter and Saturn in the natal houses that touch `year`.

    A body that goes back into a house it left is one stay with several
    segments. Needs the natal cusps, so only with a known birth time.
    """
    zone = ZoneInfo(tz)
    bounds = (date(year, 1, 1), date(year, 12, 31))
    grid = _grid(bounds[0] - timedelta(days=_HOUSE_MARGIN_DAYS), bounds[1] + timedelta(days=_HOUSE_MARGIN_DAYS))
    periods: list[dict] = []
    for body in bodies:
        def house_at(t: float, body=body) -> int:
            return _which_house(tropical_longitude(t, body), house_cusps)

        houses = [house_at(jd) for jd in grid]
        stays: list[dict] = []
        i = 0
        while i < len(grid):
            j = i
            while j + 1 < len(grid) and houses[j + 1] == houses[i]:
                j += 1
            if i > 0 and j < len(grid) - 1:
                stays.append({
                    "house": houses[i],
                    "start_jd": bisect_change(house_at, grid[i - 1], grid[i]),
                    "end_jd": bisect_change(house_at, grid[j], grid[j + 1]),
                })
            i = j + 1
        by_house: dict[int, list[dict]] = {}
        for stay in stays:
            by_house.setdefault(stay["house"], []).append(stay)
        for house, items in by_house.items():
            for group in _group(items, _DEFAULT_LOOP_GAP_DAYS):
                start_day = _local_date(group[0]["start_jd"], zone)
                end_day = _local_date(group[-1]["end_jd"], zone)
                if end_day < bounds[0] or start_day > bounds[1]:
                    continue
                periods.append({
                    "id": f"{body.lower()}-house-{house}",
                    "kind": "house",
                    "body": body,
                    "house": house,
                    "start": start_day.isoformat(),
                    "end": end_day.isoformat(),
                    "starts_before_year": start_day < bounds[0],
                    "ends_after_year": end_day > bounds[1],
                    "segments": [
                        {
                            "start": _local_date(s["start_jd"], zone).isoformat(),
                            "end": _local_date(s["end_jd"], zone).isoformat(),
                            "retrograde_entry": longitude_speed(s["start_jd"], body) < 0.0,
                        }
                        for s in group
                    ],
                })
    periods.sort(key=lambda p: (p["start"], p["body"]))
    return periods


# --------------------------------------------------------- retrograde periods

def retrograde_periods(year: int, tz: str = "Europe/Warsaw", bodies: tuple[str, ...] = RETROGRADE_BODIES) -> list[dict]:
    """Retrograde stretches touching `year`: the same for everyone."""
    zone = ZoneInfo(tz)
    bounds = (date(year, 1, 1), date(year, 12, 31))
    jd_from = julian_day_at_noon(bounds[0] - timedelta(days=200))
    jd_to = julian_day_at_noon(bounds[1] + timedelta(days=200))
    periods = []
    for body in bodies:
        stations = _stations(body, jd_from, jd_to, 1.0)
        for (moment, kind), following in zip(stations, stations[1:]):
            if kind != "retrograde" or following[1] != "direct":
                continue
            start_day, end_day = _local_date(moment, zone), _local_date(following[0], zone)
            if end_day < bounds[0] or start_day > bounds[1]:
                continue
            periods.append({
                "id": f"{body.lower()}-retrograde-{start_day.isoformat()}",
                "kind": "retrograde",
                "body": body,
                "start": start_day.isoformat(),
                "end": end_day.isoformat(),
                "start_utc": jd_to_moment(moment),
                "end_utc": jd_to_moment(following[0]),
                "sign_start": sign_of(tropical_longitude(moment, body)),
                "sign_end": sign_of(tropical_longitude(following[0], body)),
            })
    periods.sort(key=lambda p: (p["start"], p["body"]))
    return periods


# ------------------------------------------------------------------ eclipses

_SOLAR_TYPES = ((swe.ECL_TOTAL, "total"), (swe.ECL_ANNULAR, "annular"), (swe.ECL_PARTIAL, "partial"))
_LUNAR_TYPES = ((swe.ECL_TOTAL, "total"), (swe.ECL_PARTIAL, "partial"), (swe.ECL_PENUMBRAL, "penumbral"))
if hasattr(swe, "ECL_ANNULAR_TOTAL"):
    _SOLAR_TYPES = ((swe.ECL_ANNULAR_TOTAL, "hybrid"), *_SOLAR_TYPES)


def _eclipse_type(flags: int, table) -> str:
    return next((name for bit, name in table if flags & bit), "partial")


def eclipses(year: int, points: list[dict] | None = None, tz: str = "Europe/Warsaw") -> list[dict]:
    """Solar and lunar eclipses of `year`, with their contacts to the natal points.

    A contact is a conjunction or an opposition within `ECLIPSE_ORB` of the
    eclipsed body (the Sun for a solar eclipse, the Moon for a lunar one).
    """
    zone = ZoneInfo(tz)
    bounds = (date(year, 1, 1), date(year, 12, 31))
    start = julian_day_at_noon(bounds[0] - timedelta(days=1))
    found = []
    for kind, search, table, body in (
        ("solar", swe.sol_eclipse_when_glob, _SOLAR_TYPES, "Sun"),
        ("lunar", swe.lun_eclipse_when, _LUNAR_TYPES, "Moon"),
    ):
        jd = start
        while True:
            flags, times = search(jd)
            moment = float(times[0])
            day = _local_date(moment, zone)
            if day > bounds[1]:
                break
            jd = moment + 10.0
            if day < bounds[0]:
                continue
            longitude = tropical_longitude(moment, body)
            contacts = []
            for point in points or []:
                if point["name"] not in NATAL_TARGETS:
                    continue
                for angle, aspect in ((0.0, "Conjunction"), (180.0, "Opposition")):
                    orb = _orb_to(point, longitude, angle)
                    if orb <= ECLIPSE_ORB:
                        contacts.append({"target": point["name"], "aspect": aspect, "orb": round(orb, 2)})
            found.append({
                "id": f"eclipse-{kind}-{day.isoformat()}",
                "kind": kind,
                "type": _eclipse_type(int(flags), table),
                **_stamp(moment, zone),
                "sign": sign_of(longitude),
                "degree": round(longitude % 30.0, 2),
                "contacts": contacts,
            })
    found.sort(key=lambda e: e["date"])
    return found


# ------------------------------------------------------------- personal year

def personal_months(birth_date: date, year: int) -> dict:
    """Personal Year of `year` and its twelve Personal Months.

    A Personal Month is the Personal Year plus the calendar month, reduced the
    same way (11, 22 and 33 kept).
    """
    personal_year = compute_personal_year(birth_date, date(year, 1, 1))
    return {
        "personal_year": personal_year,
        "months": [{"month": m, "number": _digit_sum(personal_year + m)} for m in range(1, 13)],
    }


# --------------------------------------------------------------- BaZi months

def _sun_term(jd_guess: float, target: float) -> float:
    jd = jd_guess
    for _ in range(30):
        delta = (_bazi._sun_longitude(jd) - target + 180.0) % 360.0 - 180.0
        if abs(delta) < 1e-7:
            break
        jd -= delta / 0.9856
    return jd


def _pillar_entry(pillar: str, day_master: str, natal_branches: dict[str, str]) -> dict:
    info = _bazi._pillar_info(pillar, day_master)
    branch = pillar[1]
    return {
        "pillar": pillar,
        "stem": info["stem"],
        "branch": info["branch"],
        "stem_ten_god": info["ten_gods"]["stem_ten_god"],
        "hidden_ten_gods": [h["ten_god"] for h in info["ten_gods"]["hidden_stems_ten_gods"]],
        "clashes": sorted(name for name, natal in natal_branches.items() if BRANCH_CLASHES[branch] == natal),
    }


def bazi_months(
    year: int,
    day_master: str,
    natal_branches: dict[str, str] | None = None,
    tz: str = "Europe/Warsaw",
) -> dict:
    """The BaZi year that starts at Li Chun of `year`, and every BaZi month in force
    during the calendar year, each from the moment of its opening solar term.

    `day_master` is the Day Master stem (hanzi); `natal_branches` maps a label
    (``"day"``, ``"year"``) to the natal branch it is checked against for a clash.
    The month stems follow the five-tigers rule from the year stem.
    """
    zone = ZoneInfo(tz)
    natal_branches = natal_branches or {}
    bounds = (date(year, 1, 1), date(year, 12, 31))
    jd = _bazi._jie_julian_day(julian_day_at_noon(bounds[0]), forward=False)
    months = []
    while _local_date(jd, zone) <= bounds[1]:
        longitude = round(_bazi._sun_longitude(jd)) % 360
        k = int(round(((longitude - 315) % 360) / 30.0)) % 12  # 0 = 寅 month (Li Chun)
        gregorian = jd_to_datetime(jd).year
        bazi_year = gregorian - 1 if k == 11 and jd_to_datetime(jd).month <= 2 else gregorian
        year_stem = (bazi_year - 4) % 10
        stem = ((year_stem % 5) * 2 + 2 + k) % 10
        branch = _BRANCHES[(2 + k) % 12]
        pillar = _bazi.HEAVENLY_STEMS_HANZI[stem] + branch
        months.append({**_stamp(jd, zone), "bazi_year": bazi_year, **_pillar_entry(pillar, day_master, natal_branches)})
        jd = _sun_term(jd + 30.4, (longitude + 30) % 360)
    li_chun = next(m for m in months if m["branch"]["hanzi"] == "寅")
    year_pillar = _bazi.HEAVENLY_STEMS_HANZI[(year - 4) % 10] + _BRANCHES[(year - 4) % 12]
    return {
        "year": {"date": li_chun["date"], "moment_utc": li_chun["moment_utc"], **_pillar_entry(year_pillar, day_master, natal_branches)},
        "months": months,
    }
