"""Karmic indicators from the birth date (plan „Kundalini i Karma”, session SE).

One call for the Admin panel (Michael Teachings → Karma, section E). Every value
comes from an existing engine function; this module only gathers them:

* numerology — karmic debts 13/14/16/19 and karmic lessons
  (`numerology.compute_karmic_debts`, `numerology.compute_karmic_lessons`);
* Matrix of Destiny — the karmic tail and vertex B, external karma
  (`matrix_destiny.compute_karmic_points`);
* lunar nodes — the sign of the true node, tropical and sidereal
  (`ephemeris.compute_lunar_node_signs`).

The definitions were agreed with the owner on 2026-11-19 and are documented in
each function. Nothing here feeds the existing reports or the public API.
"""

from __future__ import annotations

from datetime import date

from eldermind_core.services.ephemeris import compute_lunar_node_signs
from eldermind_core.services.matrix_destiny import compute_karmic_points
from eldermind_core.services.numerology import compute_karmic_debts, compute_karmic_lessons

#: Shape version of `compute_karmic_indicators`; bump when a key changes.
KARMIC_INDICATORS_SCHEMA = 1


def compute_karmic_indicators(birth_date: date, full_name: str | None = None) -> dict:
    """All karmic indicators for one person.

    Args:
        birth_date: The local birth date.
        full_name: Full name from birth (all given names and the birth
            surname). Optional; without it the name numbers and the karmic
            lessons are ``None``.

    Returns:
        ``{"schema_version", "has_name", "numerology": {"karmic_debts",
        "karmic_lessons"}, "matrix": {"karmic_tail", "external_karma"},
        "lunar_nodes": {...}}``.
    """
    has_name = bool(full_name and full_name.strip())
    return {
        "schema_version": KARMIC_INDICATORS_SCHEMA,
        "has_name": has_name,
        "numerology": {
            "karmic_debts": compute_karmic_debts(birth_date, full_name if has_name else None),
            "karmic_lessons": compute_karmic_lessons(full_name) if has_name else None,
        },
        "matrix": compute_karmic_points(birth_date),
        "lunar_nodes": compute_lunar_node_signs(birth_date),
    }
