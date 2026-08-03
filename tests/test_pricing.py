"""Tests for the credit price list.

Pricing had no tests at all until now, which is odd for the one part of the
engine that decides what a customer is charged. A wrong aspect orb produces a
questionable reading; a wrong price produces a refund, an angry email, or
silent under-billing nobody notices for months.

These pin the *decisions*, not the arithmetic: that Vedic is dearer because it
does more work, that the bundle is a real discount rather than a rounding
artefact, and that a transit scan is charged by the span it covers. Each one is
a claim the pricing page makes to a buyer in public.
"""

from __future__ import annotations

import pytest

from eldermind_core.profile import (
    ALL_SYSTEMS,
    MAX_TRANSIT_MONTHS,
    credits_for,
    credits_for_transits,
)

# --- Per-system prices -----------------------------------------------------


@pytest.mark.parametrize(
    "system",
    ["western", "human_design", "gene_keys", "matrix", "bazi", "numerology", "draconic"],
)
def test_light_systems_cost_one_credit(system: str) -> None:
    """The seven the pricing page groups as "one light system"."""
    assert credits_for([system]) == 1


def test_vedic_costs_two_because_it_does_more_work() -> None:
    """~30 ms against under 1 ms for BaZi: the Dasha timeline is not free.

    This is the only single system priced above one, and the page says so out
    loud. If it ever silently becomes 1, the engine is giving away the Vimshottari
    computation.
    """
    assert credits_for(["vedic"]) == 2


def test_an_unknown_system_falls_back_to_one_rather_than_free() -> None:
    """A system added to the engine but forgotten here must still bill.

    Defaulting to zero would mean a new endpoint quietly serving free compute
    until someone noticed the revenue gap.
    """
    assert credits_for(["a_system_added_later"]) == 1


# --- Combinations ----------------------------------------------------------


def test_a_subset_costs_the_sum_of_its_parts() -> None:
    assert credits_for(["bazi", "numerology"]) == 2
    assert credits_for(["vedic", "bazi"]) == 3


def test_price_does_not_depend_on_order_or_repetition() -> None:
    """Callers pass lists; the price is a property of the set they name."""
    assert credits_for(["bazi", "vedic"]) == credits_for(["vedic", "bazi"])
    assert credits_for(["bazi", "bazi", "bazi"]) == credits_for(["bazi"])


def test_nothing_requested_costs_nothing() -> None:
    assert credits_for([]) == 0


# --- The bundle discount ---------------------------------------------------


def test_the_bundle_is_six() -> None:
    assert credits_for(ALL_SYSTEMS) == 6


def test_the_bundle_really_is_cheaper_than_calling_the_systems_separately() -> None:
    """The discount is the whole reason the bundle exists.

    It steers a model towards one tool call instead of eight, which is faster
    for the user and cheaper for us because the ephemeris work is shared. If
    the separate prices ever drift below the bundle, that incentive inverts and
    the MCP instructions start giving bad advice.
    """
    separately = sum(credits_for([system]) for system in ALL_SYSTEMS)

    assert separately == 9
    assert credits_for(ALL_SYSTEMS) < separately


def test_the_discount_needs_the_whole_set() -> None:
    """Seven of eight is not a bundle, and must not be priced as one."""
    seven = list(ALL_SYSTEMS)[:-1]

    assert credits_for(seven) > credits_for(ALL_SYSTEMS)


# --- Transits --------------------------------------------------------------


@pytest.mark.parametrize("months", [1, 3, 12, 18, MAX_TRANSIT_MONTHS])
def test_transits_cost_one_credit_per_month(months: int) -> None:
    """Linear because the work is: the scan steps day by day through the span."""
    assert credits_for_transits(months) == months


def test_a_transit_scan_is_never_free() -> None:
    assert credits_for_transits(1) >= 1


@pytest.mark.parametrize("months", [0, -1, -12])
def test_a_non_positive_span_is_rejected_rather_than_charged_zero(months: int) -> None:
    """Silently pricing a nonsense span at zero would hand out free compute."""
    with pytest.raises(ValueError):
        credits_for_transits(months)


def test_a_month_of_transits_outprices_a_light_system() -> None:
    """~67 ms per month against ~5 ms: the ordering has to survive any retune.

    Stated as a relationship rather than as two numbers, because the point is
    not that transits cost 1 — it is that the heaviest operation must never
    become cheaper per unit than the lightest one, which is exactly what the
    old flat rate of 5 credits for an 18-month scan did.
    """
    assert credits_for_transits(1) >= credits_for(["western"])


def test_a_full_span_scan_outprices_the_whole_bundle() -> None:
    """24 months is ~1.6 s of CPU against ~41 ms for all eight systems."""
    assert credits_for_transits(MAX_TRANSIT_MONTHS) > credits_for(ALL_SYSTEMS)


def test_the_span_ceiling_is_a_usable_range() -> None:
    """A ceiling below a year would make the endpoint useless for its purpose;
    an unbounded one would let a single call hold the only vCPU for a minute."""
    assert 12 <= MAX_TRANSIT_MONTHS <= 60
