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
from typing import Any

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


__all__ = ["AVAILABLE", "KNOWLEDGE_DIR", "load"]
