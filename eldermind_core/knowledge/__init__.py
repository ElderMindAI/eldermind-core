"""Static knowledge base shipped with the engine (~1 MB of JSON).

Descriptive content only — gate/channel/line/centre texts, Gene Keys, HD types,
authorities and profiles. Nothing here participates in a calculation; it is what
turns a gate number into something a human (or a model) can read.

Access it through :func:`load` rather than by building paths, so consumers keep
working when the package is installed as a wheel or zipped into a container.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

#: Directory holding the JSON files. Prefer :func:`load` over touching this.
KNOWLEDGE_DIR: Path = Path(__file__).resolve().parent

#: Logical name -> file name. The API exposes these as `/v1/knowledge/{system}`.
AVAILABLE: dict[str, str] = {
    "animal_design": "animal_design_kb.json",
    "gene_keys": "gene_keys.json",
    "hd_authorities": "hd_authorities.json",
    "hd_centers": "hd_centers.json",
    "hd_channels": "hd_channels.json",
    "hd_gates": "hd_gates.json",
    "hd_lines": "hd_lines.json",
    "hd_profiles": "hd_profiles.json",
    "hd_types": "hd_types.json",
}


@lru_cache(maxsize=None)
def load(name: str) -> dict[str, Any]:
    """Return a knowledge file by logical name or by bare file name.

    Cached: these files are read-only and total ~1 MB, so paying the parse cost
    once per process is strictly better than per request. Returns an empty dict
    when the file is absent, matching the previous behaviour of the report
    backend's RAG layer, which degrades rather than failing a whole report.
    """
    file_name = AVAILABLE.get(name, name)
    if not file_name.endswith(".json"):
        file_name = f"{file_name}.json"

    path = KNOWLEDGE_DIR / file_name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


#: Incarnation cross names (PL/EN). Deliberately NOT in :data:`AVAILABLE`, which the public API
#: serves as `/v1/knowledge/{system}` — the report uses it first; exposing it is a separate decision.
INCARNATION_CROSSES_FILE = "hd_incarnation_crosses.json"


@lru_cache(maxsize=1)
def _crosses_by_key() -> dict[tuple[str, int], dict[str, Any]]:
    data = load(INCARNATION_CROSSES_FILE)
    return {(c["angle"], c["gates"][0]): c for c in data.get("crosses", [])}


def incarnation_cross(angle: str, gates: Sequence[int]) -> dict[str, Any] | None:
    """Look up the name of an incarnation cross.

    ``angle`` and ``gates`` are the engine's ``mechanics.incarnation_cross_angle`` ("Right Angle",
    "Left Angle", "Juxtaposition") and ``mechanics.incarnation_cross_gates`` ([Personality Sun,
    Personality Earth, Design Sun, Design Earth]). Returns the entry (``name_pl``, ``name_en``,
    ``variant``, ``gates``, ``source_url``) or ``None`` when the cross is unknown or its four gates
    differ from the table — never a name for a different cross.
    """
    gates = [int(g) for g in gates]
    if len(gates) != 4:
        return None
    entry = _crosses_by_key().get((angle, gates[0]))
    if entry is None or list(entry["gates"]) != gates:
        return None
    return dict(entry)


__all__ = ["AVAILABLE", "INCARNATION_CROSSES_FILE", "KNOWLEDGE_DIR", "incarnation_cross", "load"]
