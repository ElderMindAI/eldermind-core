"""Detail levels — the fix for bloker B6.

A full profile is ~29 KB of JSON, roughly 8 000 tokens. Handed to a model as a
tool result, one call eats a large slice of the context window before the model
has said anything. So the engine can project the same data at three depths:

    summary   ~1.5 KB   only conclusions          <- MCP default
    standard  ~8 KB     positions, no history     <- REST default
    full      ~29 KB    everything                <- export, backend-to-backend

This is projection, not recomputation: the cost is the same, only the payload
shrinks. That matters for the cache — one computed profile serves all three
levels.

`summary` is written for a reader, not a parser. `"Generator"`, not `"type_2"`;
a Dasha as a period with dates, not a hundred-year table. A model that needs
more can ask for `standard`.
"""

from __future__ import annotations

from typing import Any

#: Ordered from cheapest to richest.
DETAIL_LEVELS: tuple[str, ...] = ("summary", "standard", "full")


def _first(items: Any, *keys: str) -> Any:
    """Return the first present key from a dict, or None."""
    if not isinstance(items, dict):
        return None
    for key in keys:
        if key in items and items[key] is not None:
            return items[key]
    return None


def _body(planets: Any, name: str) -> dict[str, Any] | None:
    if not isinstance(planets, list):
        return None
    for planet in planets:
        if isinstance(planet, dict) and planet.get("name") == name:
            return planet
    return None


def _placement(planets: Any, name: str) -> str | None:
    """Render one body as `Leo 8.74°`, or None if absent."""
    body = _body(planets, name)
    if not body:
        return None
    sign = body.get("sign")
    degree = body.get("degree_in_sign")
    if sign is None or degree is None:
        return None
    return f"{sign} {degree:.2f}°"


def _summarize_western(data: dict[str, Any]) -> dict[str, Any]:
    planets = data.get("planets")
    ascendant = data.get("ascendant") or {}
    midheaven = data.get("midheaven") or {}
    return {
        "sun": _placement(planets, "Sun"),
        "moon": _placement(planets, "Moon"),
        "ascendant": f"{ascendant.get('sign')} {ascendant.get('degree_in_sign', 0):.2f}°"
        if ascendant.get("sign")
        else None,
        "midheaven": midheaven.get("sign"),
        "retrograde_bodies": [
            planet["name"]
            for planet in (planets or [])
            if isinstance(planet, dict) and planet.get("is_retrograde")
        ],
        "aspect_count": len(data.get("aspects") or []),
    }


def _period(period: Any) -> dict[str, Any] | None:
    """Render a Dasha period as lord + dates, dropping its antardasha table."""
    if not isinstance(period, dict):
        return None
    return {
        "lord": period.get("lord"),
        "start": period.get("start"),
        "end": period.get("end"),
    }


def _summarize_vedic(data: dict[str, Any]) -> dict[str, Any]:
    dasha = data.get("vimshottari_dasha") or {}
    sade_sati = data.get("sade_sati") or {}
    chakra = data.get("avakahada_chakra") or {}
    current = dasha.get("current") or {}
    antardashas = current.get("antardashas") or []

    return {
        "ayanamsa": data.get("ayanamsa"),
        # The Moon's own sidereal sign — NOT the Ascendant's, which is what a
        # naive fallback picks up and which is wrong most of the time.
        "moon_sign": (_body(data.get("planets"), "Moon") or {}).get("sign"),
        "ascendant_sign": (data.get("ascendant") or {}).get("sign"),
        "moon_nakshatra": dasha.get("moon_nakshatra"),
        "nakshatra_lord": dasha.get("moon_nakshatra_lord"),
        "current_mahadasha": _period(current),
        "current_antardasha": _period(antardashas[0]) if antardashas else None,
        "sade_sati": {
            "status": sade_sati.get("status"),
            "phase": sade_sati.get("phase"),
            "start_date": sade_sati.get("start_date"),
            "end_date": sade_sati.get("end_date"),
        },
        "gana": chakra.get("gana"),
        "nadi": chakra.get("nadi"),
    }


def _summarize_human_design(data: dict[str, Any]) -> dict[str, Any]:
    mechanics = data.get("mechanics") or {}
    source = mechanics if mechanics else data
    return {
        "type": source.get("type"),
        "strategy": source.get("strategy"),
        "authority": source.get("authority"),
        "profile": source.get("profile"),
        "definition": source.get("definition"),
        "defined_centers": source.get("defined_centers"),
        "channel_count": len(source.get("channels") or []),
        "incarnation_cross_gates": _first(
            source, "incarnation_cross_gates", "incarnation_cross"
        ),
    }


def _summarize_gene_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Keep only the four Activation spheres — the entry point of the profile.

    Rendered as `"40.4"` (gene key . line) because that is how the system is
    written and read; the longitude and body that produced it are noise here.
    """
    activation = _first(data, "activation_sequence", "activation") or {}
    spheres = {}
    if isinstance(activation, dict):
        for name, sphere in activation.items():
            if isinstance(sphere, dict):
                key = sphere.get("gene_key", sphere.get("gate"))
                line = sphere.get("line")
                spheres[name] = f"{key}.{line}" if key and line else None
    return {"activation_sequence": spheres}


def _summarize_matrix(data: dict[str, Any]) -> dict[str, Any]:
    timeline = data.get("timeline") or {}
    return {
        "core": data.get("core"),
        "personal_destiny_40": data.get("personal_destiny_40"),
        "personal_destiny_40_name": data.get("personal_destiny_40_name"),
        "current_age": timeline.get("current_age"),
        "highlighted_decade": timeline.get("highlighted_decade"),
    }


def _summarize_bazi(data: dict[str, Any]) -> dict[str, Any]:
    day_master = data.get("day_master") or {}
    useful_god = data.get("useful_god") or {}
    return {
        "day_master": _stem_label(day_master),
        "year_pillar": _pillar(data.get("year_pillar")),
        "month_pillar": _pillar(data.get("month_pillar")),
        "day_pillar": _pillar(data.get("day_pillar")),
        "hour_pillar": _pillar(data.get("hour_pillar")),
        "day_master_strength": useful_god.get("day_master_strength"),
        "useful_element": useful_god.get("useful_element"),
        "element_count": data.get("element_count"),
    }


def _stem_label(stem: Any) -> str | None:
    """Render a heavenly stem as `Yi (Yin Wood)` — readable without a lookup table."""
    if not isinstance(stem, dict):
        return stem if isinstance(stem, str) else None
    name = _first(stem, "english", "name", "hanzi")
    polarity = stem.get("polarity")
    element = stem.get("element")
    if name is None:
        return None
    if polarity and element:
        return f"{name} ({polarity} {element})"
    return str(name)


def _branch_label(branch: Any) -> str | None:
    """Render an earthly branch as `Rooster (Yin Metal)`."""
    if not isinstance(branch, dict):
        return branch if isinstance(branch, str) else None
    name = _first(branch, "animal", "english", "name", "hanzi")
    polarity = branch.get("polarity")
    element = branch.get("element")
    if name is None:
        return None
    if polarity and element:
        return f"{name} ({polarity} {element})"
    return str(name)


def _pillar(pillar: Any) -> dict[str, Any] | None:
    """Render a BaZi pillar without its Ten Gods breakdown."""
    if not isinstance(pillar, dict):
        return None
    return {
        "stem": _stem_label(pillar.get("stem")),
        "branch": _branch_label(pillar.get("branch")),
    }


def _summarize_draconic(data: dict[str, Any]) -> dict[str, Any]:
    planets = data.get("planets")
    return {
        "north_node_longitude": _first(data, "north_node_longitude", "node_longitude"),
        "sun": _placement(planets, "Sun"),
        "moon": _placement(planets, "Moon"),
    }


_SUMMARIZERS = {
    "western": _summarize_western,
    "vedic": _summarize_vedic,
    "human_design": _summarize_human_design,
    "gene_keys": _summarize_gene_keys,
    "matrix": _summarize_matrix,
    "bazi": _summarize_bazi,
    "numerology": lambda data: data,  # Already 7 numbers; nothing to trim.
    "draconic": _summarize_draconic,
}

#: Fields dropped at `standard`: long historical tables that only an export needs.
#: `timeline` is the 100-year Vimshottari table, `da_yun` the ten-year luck
#: pillars — together most of the payload, and useful to almost no caller who
#: is not building their own chart software.
_STANDARD_DROPS = {
    "vedic": ("timeline",),
    "bazi": ("da_yun",),
    "human_design": ("personality", "design"),
}


def _prune(data: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(data, dict):
        return data
    pruned = {key: value for key, value in data.items() if key not in keys}
    # Nested one level: the Dasha table hangs off `vimshottari_dasha`.
    for key, value in pruned.items():
        if isinstance(value, dict):
            pruned[key] = {k: v for k, v in value.items() if k not in keys}
    return pruned


def apply_detail(payload: dict[str, Any], detail: str = "standard") -> dict[str, Any]:
    """Project a full profile payload down to the requested level.

    Args:
        payload: Output of `ProfileResult.to_dict()`.
        detail: One of `DETAIL_LEVELS`. Unknown values fall back to `standard`
            rather than raising — a client on a newer API version asking for a
            level this engine does not know should get data, not a 400.

    Returns:
        A new dict. The input is not modified, so the same computed profile can
        be served at several levels from one cache entry.
    """
    if detail not in DETAIL_LEVELS:
        detail = "standard"
    if detail == "full":
        return payload

    projected: dict[str, Any] = {"meta": {**payload.get("meta", {}), "detail": detail}}

    for key, value in payload.items():
        if key == "meta":
            continue
        if detail == "summary":
            summarizer = _SUMMARIZERS.get(key)
            projected[key] = summarizer(value) if summarizer and isinstance(value, dict) else value
        else:
            projected[key] = _prune(value, _STANDARD_DROPS.get(key, ()))

    return projected


__all__ = ["DETAIL_LEVELS", "apply_detail"]
