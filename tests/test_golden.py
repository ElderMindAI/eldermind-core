"""Golden tests — the contract with every paying client (§7.3 of the plan).

Twenty-three subjects, each with its full multi-system response frozen on disk.
Any engine change that moves a single number fails here, loudly, with the exact
path that moved. That is the point: a client who cached a chart last month must
get the same chart today unless we deliberately decided otherwise.

The set is chosen for the places calculations actually break, not for coverage
theatre: daylight-saving gaps and overlaps, the polar circles where Placidus
degenerates, 29 February, dates before 1900 (when Warsaw ran on +01:24 local
mean time), the 180th meridian, UTC+14, the equator, and the half- and
quarter-hour offsets of India and Nepal.

To change a golden file deliberately: `python tools/regenerate_golden.py --write`,
then read the diff before committing.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.golden_support import compute_case, dump, expected_path, load_cases

CASES = load_cases()
CASE_IDS = [case["id"] for case in CASES]


def _diff_paths(expected: Any, actual: Any, prefix: str = "") -> list[str]:
    """Return the paths where two nested structures disagree.

    A raw assertion on two 30 KB dicts is unreadable. This points at the exact
    fields that moved, which is what makes a golden failure actionable.
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        paths: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in expected:
                paths.append(f"{child}  (added)")
            elif key not in actual:
                paths.append(f"{child}  (removed)")
            else:
                paths.extend(_diff_paths(expected[key], actual[key], child))
        return paths

    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{prefix}  (length {len(expected)} -> {len(actual)})"]
        paths = []
        for index, (exp, act) in enumerate(zip(expected, actual)):
            paths.extend(_diff_paths(exp, act, f"{prefix}[{index}]"))
        return paths

    if expected != actual:
        return [f"{prefix}: {expected!r} -> {actual!r}"]
    return []


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_golden_response_is_unchanged(case: dict[str, Any]) -> None:
    path = expected_path(case["id"])
    assert path.exists(), (
        f"Missing golden file for {case['id']!r}. "
        f"Run: python tools/regenerate_golden.py --write"
    )

    actual = dump(compute_case(case))
    expected = path.read_text(encoding="utf-8")
    if actual == expected:
        return

    import json

    differences = _diff_paths(json.loads(expected), json.loads(actual))
    listed = "\n  ".join(differences[:25])
    more = f"\n  ... and {len(differences) - 25} more" if len(differences) > 25 else ""
    pytest.fail(
        f"Engine output changed for {case['id']!r} ({case['note']}):\n  {listed}{more}\n\n"
        f"If this change is intended, bump ENGINE_VERSION and re-freeze with "
        f"`python tools/regenerate_golden.py --write`."
    )


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.get("expect_error")], ids=lambda c: c["id"]
)
def test_expected_failures_still_fail(case: dict[str, Any]) -> None:
    """Cases that must be rejected are rejected, with the documented code."""
    result = compute_case(case)
    assert "error" in result, f"{case['id']} was expected to fail but computed a chart"
    assert result["error"]["code"] == case["expect_error"]


def test_every_case_has_a_unique_id() -> None:
    assert len(CASE_IDS) == len(set(CASE_IDS))


def test_edge_cases_are_actually_covered() -> None:
    """Guard against someone quietly deleting the awkward subjects."""
    required = {
        "dst-gap-spring",
        "dst-fold-autumn",
        "polar-tromso",
        "leap-day-1992",
        "pre-1900-warsaw",
        "meridian-180-fiji",
        "date-out-of-range",
        "no-birth-time",
        "no-name",
    }
    assert required <= set(CASE_IDS)
