"""Shared loading logic for the golden tests and the regeneration script.

Kept in one place so the frozen files can never be produced by different code
than the code that checks them — that is the failure mode which turns a golden
suite into decoration.
"""

from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path
from typing import Any

from eldermind_core.core.errors import EldermindCoreError
from eldermind_core.profile import Subject, compute_profile

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
SUBJECTS_PATH = GOLDEN_DIR / "subjects.json"
EXPECTED_DIR = GOLDEN_DIR / "expected"

#: Frozen so "today" can never leak into a golden file. Every date-dependent
#: system (Dasha, Sade Sati, Personal Year, Matrix decade) is computed against
#: this date — that is the whole point of bloker B1.
GOLDEN_REFERENCE_DATE = date(2026, 7, 31)


def load_cases() -> list[dict[str, Any]]:
    return json.loads(SUBJECTS_PATH.read_text(encoding="utf-8"))


def build_subject(case: dict[str, Any]) -> Subject:
    raw_time = case.get("birth_time")
    return Subject(
        birth_date=date.fromisoformat(case["birth_date"]),
        latitude=case["latitude"],
        longitude=case["longitude"],
        timezone=case["timezone"],
        birth_time=time.fromisoformat(raw_time) if raw_time else None,
        birth_time_unknown=case.get("birth_time_unknown", False),
        gender=case.get("gender"),
        full_name=case.get("full_name"),
        reference_date=GOLDEN_REFERENCE_DATE,
    )


def compute_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run one case and return its comparable payload.

    Cases that are supposed to fail return the error envelope instead of a
    chart, so a regression that stops raising is caught just as loudly as one
    that changes a number.
    """
    subject = build_subject(case)
    strict = case.get("strict", True)
    try:
        payload = compute_profile(subject, strict=strict).to_dict()
    except EldermindCoreError as exc:
        return {"error": exc.to_dict()}

    # Wall-clock timing is the one field that legitimately differs run to run.
    payload["meta"].pop("computed_ms", None)
    return payload


def expected_path(case_id: str) -> Path:
    return EXPECTED_DIR / f"{case_id}.json"


def dump(payload: dict[str, Any]) -> str:
    """Serialise deterministically: stable key order, no ASCII escaping."""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
