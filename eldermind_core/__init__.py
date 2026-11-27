"""Eldermind Core — deterministic esoteric calculation engine.

Pure computation only: no LLM calls, no database, no HTTP framework, no PDF
rendering. Everything here is a function of its arguments, which is what makes
the results cacheable and the API contract testable.

Consumers:
  * `Backend Calculator Engine` — the report product
  * `eldermind-astro-api`      — the public REST + MCP service

`ENGINE_VERSION` is part of every cache key and is returned in the
`X-Engine-Version` response header. Bump it whenever a change moves a number.
"""

from __future__ import annotations

__version__ = "1.0.0"

#: Version of the calculation semantics, not of the packaging. Two builds with
#: the same ENGINE_VERSION must produce byte-identical results for identical
#: inputs — the golden tests enforce this.
#: 1.0.1 (2026-10-23): BaZi Ten Gods derived from the five-element cycles —
#: the old hand-written table had 32 of 100 cells wrong.
#: 1.0.2 (2026-10-29): Da Yun starts from the pillar next to the month pillar
#: (it repeated the month pillar, shifting every decade by one) and its
#: starting age comes from the Jie solar terms instead of a 3/4-year guess.
#: 1.0.3 (2026-11-02): Avakahada Varna from the Moon's sidereal sign (water
#: Brahmin, fire Kshatriya, earth Vaishya, air Shudra), not a per-Nakshatra table.
#: 1.0.4 (2026-11-02): facts the report used to leave to the model — Nakshatra,
#: pada and lord of every Vedic body (Ketu added), houses from the Lagna and the
#: Moon, drishti, yogas and doshas with their conditions, the panchanga, every
#: Sade-Sati window of the life, Da Yun calendar years, and the bridges of a
#: split Human Design definition. No existing number moved.
#: 1.0.5 (2026-11-02): transit windows dated at the minute of each pass instead
#: of the noon of the nearest day in orb (a hit past the end of the scan was
#: clamped to its last day, one before the start to its first), every pass of a
#: retrograde loop listed, stations short of the degree marked `exact: false`,
#: one ingress per sign entered; aspects of the transits in force on the
#: reference day and the Jupiter/Saturn returns (`services/transits.py`);
#: navamsa sign of every pada, natal house of every draconic point.
#: 1.0.7 (2026-11-17): BaZi year pillar from Li Chun (the Sun at 315°, to the
#: moment in UT) instead of the Chinese New Year, which put it out of step with
#: the month pillar for births between the two; the Da Yun direction, element
#: count and Useful God follow the corrected year. The whole-day variants use
#: the same function (`bazi.four_pillars`).
#: 1.0.8 (2026-11-17): BaZi month pillar from the Jie to the moment in UT
#: (the Sun at 315° + 30°k), its stem by 五虎遁 from the year stem. cnlunar
#: opened the month at local midnight of the Beijing date of the Jie: for
#: births in Poland up to ~18 h early or ~7 h late, about 1% of all births.
#: The Da Yun pillars, which step from the month pillar, follow it.
#: 1.1.0 (2026-11-27): the full Matrix of Destiny — `octagram` (8 vertices,
#: two inner points per ray), `heart_points`, `love_money`, the 0-80 `age_ring`
#: (64 points every 1.25 years by recursive midpoint), `current_point` and
#: `next_point`. `timeline.decades` now reads the ring vertex reached at each
#: age (20 top, 30 top-right, 40 right, 50 bottom-right, 60 bottom); it used
#: to map right/bottom/left/center/top, which no standard chart does — every
#: decade value moves. `lines.relationship` is kept unchanged but deprecated
#: in favour of `love_money` (listed under `matrix.deprecated`).
#: Also in 1.1.0 (2026-11-28, before any deploy): Gene Keys EQ comes from the
#: Personality (natal) Mars and Core Wound/Vocation from the Design
#: (pre-natal) Mars, as the Gene Keys FAQ lists them; the two sources were
#: swapped, so EQ and Core/Vocation exchange their key.line for everyone
#: whose two Mars differ. The other nine spheres are unchanged.
ENGINE_VERSION = "1.1.0"

__all__ = ["ENGINE_VERSION", "__version__"]
