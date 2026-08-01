"""The 8-in-1 bundle: one subject in, every system out.

This is the shape the public API sells as `POST /v1/profile/complete` and the MCP
tool `get_complete_profile` — and, not coincidentally, the shape the golden tests
freeze. Keeping it here rather than in the API layer means the contract is
defined once, in the same place as the calculations it describes.

Two properties matter, and both come from the blocker fixes in the plan:

* **Deterministic.** `Subject.reference_date` is threaded into every
  date-dependent system, so the same subject yields the same bytes forever
  (bloker B1). That is what makes the response cacheable and testable.
* **Partially successful.** One system failing must not cost the caller the
  other seven. Failures land in `meta.errors[]` and the rest returns 200
  (§3.4 of the product plan).
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Callable, Iterable, Sequence

from eldermind_core import ENGINE_VERSION
from eldermind_core.core.errors import EldermindCoreError
from eldermind_core.core.reference import assert_date_in_range, resolve_reference_date
from eldermind_core.services.bazi import compute_bazi
from eldermind_core.services.ephemeris import (
    attach_houses_to_planets,
    compute_all_planets,
    compute_draconic_chart,
    compute_houses,
    compute_julian_day_ut,
    compute_vedic_chart,
    compute_western_aspects,
    describe_local_time_anomaly,
)
from eldermind_core.services.gene_keys import compute_gene_keys
from eldermind_core.services.human_design import compute_human_design
from eldermind_core.services.matrix_destiny import compute_matrix_of_destiny
from eldermind_core.services.numerology import compute_numerology

#: Canonical system keys, in the order they appear in a bundle response.
ALL_SYSTEMS: tuple[str, ...] = (
    "western",
    "vedic",
    "human_design",
    "gene_keys",
    "matrix",
    "bazi",
    "numerology",
    "draconic",
)

#: Used when the caller does not know the birth time. Noon minimises the error
#: on the Moon and on the day pillar, and every time-sensitive field is flagged
#: in `warnings` so a consumer cannot quietly treat it as reliable.
DEFAULT_BIRTH_TIME = time(12, 0)

_TIME_SENSITIVE_NOTE = (
    "Birth time was not supplied; 12:00 local was assumed. The Ascendant, "
    "house cusps, the BaZi hour pillar and fast-moving bodies (especially the "
    "Moon) are unreliable in this chart."
)


@dataclass(frozen=True)
class Subject:
    """Everything the engine needs about one person.

    Deliberately a plain dataclass, not a Pydantic model: the engine must not
    depend on a web framework's validation library. The API layer validates and
    then hands one of these down.
    """

    birth_date: date
    latitude: float
    longitude: float
    timezone: str
    birth_time: time | None = None
    birth_time_unknown: bool = False
    gender: str | None = None
    full_name: str | None = None
    reference_date: date | None = None

    @property
    def effective_birth_time(self) -> time:
        return self.birth_time if self.birth_time is not None else DEFAULT_BIRTH_TIME

    @property
    def time_is_assumed(self) -> bool:
        return self.birth_time is None or self.birth_time_unknown


@dataclass
class ProfileResult:
    """Bundle output: per-system payloads plus the metadata that explains them."""

    systems: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reference_date: date | None = None
    computed_ms: int = 0
    julian_day_ut: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "engine_version": ENGINE_VERSION,
                "reference_date": self.reference_date.isoformat()
                if self.reference_date
                else None,
                "julian_day_ut": round(self.julian_day_ut, 8),
                "computed_ms": self.computed_ms,
                "warnings": self.warnings,
                "errors": self.errors,
            },
            **jsonable(self.systems),
        }


def jsonable(value: Any) -> Any:
    """Convert engine output to something `json.dumps` accepts.

    Several services return real `date`/`time` objects — convenient in Python,
    useless over HTTP. The report backend hid this because Pydantic serialised
    on the way out; the bundle has no such layer, so it normalises here. ISO 8601
    throughout, matching §3 of the product plan.
    """
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (date, time)):
        return value.isoformat()
    return value


def compute_profile(
    subject: Subject,
    systems: Sequence[str] = ALL_SYSTEMS,
    *,
    strict: bool = True,
) -> ProfileResult:
    """Compute the requested systems for one subject.

    Args:
        subject: Birth data and the reference date to compute against.
        systems: Which systems to run, from `ALL_SYSTEMS`. Unknown keys are
            reported in `errors` rather than raising, so a client on a newer
            API version does not get a hard failure from an older engine.
        strict: Reject ambiguous or non-existent local times (DST transitions)
            instead of silently picking a reading.

    Raises:
        EldermindCoreError: Only for failures that invalidate every system —
            a bad timezone, an out-of-range date, an impossible local time.
            Anything narrower is collected into `ProfileResult.errors`.
    """
    started = _time.perf_counter()
    assert_date_in_range(subject.birth_date)
    reference_date = resolve_reference_date(subject.reference_date)

    # A failure here is not recoverable: without a Julian Day there is no chart
    # of any kind, so it propagates instead of landing in `errors`.
    jd_ut, utc_dt = compute_julian_day_ut(
        birth_date=subject.birth_date,
        birth_time=subject.effective_birth_time,
        timezone_name=subject.timezone,
        strict=strict,
    )

    result = ProfileResult(reference_date=reference_date, julian_day_ut=jd_ut)

    if subject.time_is_assumed:
        result.warnings.append(_TIME_SENSITIVE_NOTE)
    if not strict:
        anomaly = describe_local_time_anomaly(
            utc_dt.astimezone(_zone(subject.timezone))
        )
        if anomaly:
            result.warnings.append(f"{anomaly} The earlier occurrence was used.")

    requested = list(dict.fromkeys(systems))  # de-duplicate, keep order
    unknown = [name for name in requested if name not in ALL_SYSTEMS]
    for name in unknown:
        result.errors.append(
            {
                "system": name,
                "code": "UNKNOWN_SYSTEM",
                "message": f"Unknown system {name!r}. Known systems: {', '.join(ALL_SYSTEMS)}.",
            }
        )

    # Western is computed first when anything needs it: the aspect list and the
    # house cusps are shared, and recomputing them per system would be waste.
    planets: list[dict] | None = None
    ascendant: dict | None = None
    midheaven: dict | None = None
    houses: list[dict] | None = None

    def ensure_western() -> None:
        nonlocal planets, ascendant, midheaven, houses
        if planets is not None:
            return
        ascendant, midheaven, houses = compute_houses(
            jd_ut=jd_ut, latitude=subject.latitude, longitude=subject.longitude
        )
        planets = attach_houses_to_planets(compute_all_planets(jd_ut=jd_ut), houses)

    def western() -> dict:
        ensure_western()
        return {
            "ascendant": ascendant,
            "midheaven": midheaven,
            "houses": houses,
            "planets": planets,
            "aspects": compute_western_aspects(planets),
        }

    def vedic() -> dict:
        return compute_vedic_chart(
            jd_ut=jd_ut,
            latitude=subject.latitude,
            longitude=subject.longitude,
            birth_dt=utc_dt,
            reference_date=reference_date,
        )

    human_design_cache: dict[str, Any] = {}

    def human_design() -> dict:
        if not human_design_cache:
            human_design_cache.update(compute_human_design(jd_birth_ut=jd_ut))
        return human_design_cache

    def gene_keys() -> dict:
        # Gene Keys is a projection of the Human Design activations, so it needs
        # that chart whether or not the caller asked for it explicitly.
        return compute_gene_keys(human_design())

    builders: dict[str, Callable[[], Any]] = {
        "western": western,
        "vedic": vedic,
        "human_design": human_design,
        "gene_keys": gene_keys,
        "matrix": lambda: compute_matrix_of_destiny(subject.birth_date, reference_date),
        "bazi": lambda: compute_bazi(
            subject.birth_date, subject.effective_birth_time, gender=subject.gender
        ),
        "numerology": lambda: compute_numerology(
            birth_date=subject.birth_date,
            current_date=reference_date,
            full_name=subject.full_name,
        ),
        "draconic": lambda: compute_draconic_chart(jd_ut=jd_ut),
    }

    for name in ALL_SYSTEMS:
        if name not in requested:
            continue
        try:
            result.systems[name] = builders[name]()
        except EldermindCoreError as exc:
            result.errors.append({"system": name, **exc.to_dict()})
        except Exception as exc:  # noqa: BLE001 - one system must not sink the rest
            result.errors.append(
                {
                    "system": name,
                    "code": "CALCULATION_ERROR",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )

    result.computed_ms = int((_time.perf_counter() - started) * 1000)
    return result


def _zone(timezone_name: str):
    from zoneinfo import ZoneInfo

    return ZoneInfo(timezone_name)


def credits_for(systems: Iterable[str]) -> int:
    """Credit cost of a set of systems, per §3.2 of the product plan.

    Lives next to the calculations because the pricing is derived from measured
    CPU cost — if a system gets faster or slower, this is the number to revisit.
    """
    per_system = {
        "western": 1,
        "vedic": 2,
        "human_design": 1,
        "gene_keys": 1,
        "matrix": 1,
        "bazi": 1,
        "numerology": 1,
        "draconic": 1,
    }
    requested = set(systems)
    if requested == set(ALL_SYSTEMS):
        return 6  # Bundle discount: 6 instead of 9, to steer clients to one call.
    return sum(per_system.get(name, 1) for name in requested)


__all__ = [
    "ALL_SYSTEMS",
    "DEFAULT_BIRTH_TIME",
    "ProfileResult",
    "Subject",
    "compute_profile",
    "credits_for",
    "jsonable",
]
