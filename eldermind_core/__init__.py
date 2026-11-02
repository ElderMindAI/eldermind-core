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
ENGINE_VERSION = "1.0.6"

__all__ = ["ENGINE_VERSION", "__version__"]
