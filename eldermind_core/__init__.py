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
ENGINE_VERSION = "1.0.2"

__all__ = ["ENGINE_VERSION", "__version__"]
