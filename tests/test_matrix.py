"""Unit tests for the Matrix of Destiny calculation module."""

from datetime import date

import pytest

from eldermind_core.services.matrix_destiny import compute_matrix_of_destiny


def _assert_valid_matrix_values(result: dict) -> None:
    """Shared assertion that all vertices are in the 1-22 range."""
    core = result["core"]
    for key in ("top", "left", "right", "bottom", "center"):
        assert isinstance(core[key], int)
        assert 1 <= core[key] <= 22
    assert 1 <= result["personal_destiny_40"] <= 22


def test_matrix_reduction_rule() -> None:
    """Values above 22 must be reduced by digit summing until <= 22."""
    # 1985 -> 1+9+8+5 = 23 -> 2+3 = 5 (right vertex)
    result = compute_matrix_of_destiny(date(1985, 6, 15))
    _assert_valid_matrix_values(result)
    assert result["core"]["top"] == 6
    assert result["core"]["left"] == 15  # day 15 is already <= 22, preserved as-is
    assert result["core"]["right"] == 5


def test_matrix_known_date_1993_09_01() -> None:
    """Verify a specific date from the prompt: 1 September 1993."""
    result = compute_matrix_of_destiny(date(1993, 9, 1))
    _assert_valid_matrix_values(result)

    # Expected manual calculation:
    # top (A)    = month 9
    # left (B)   = day 1
    # right (C)  = 1+9+9+3 = 22
    # bottom (D) = 9 + 1 + 22 = 32 -> 3+2 = 5
    # center (E) = 9 + 1 + 22 + 5 = 37 -> 3+7 = 10
    assert result["core"]["top"] == 9
    assert result["core"]["left"] == 1
    assert result["core"]["right"] == 22
    assert result["core"]["bottom"] == 5
    assert result["core"]["center"] == 10


def test_matrix_small_values_preserved() -> None:
    """Values already <= 22 should pass through unchanged."""
    result = compute_matrix_of_destiny(date(2000, 1, 1))
    _assert_valid_matrix_values(result)
    assert result["core"]["top"] == 1
    assert result["core"]["left"] == 1
    assert result["core"]["right"] == 2  # 2+0+0+0 = 2


def test_matrix_invalid_value_raises() -> None:
    """Values below 1 in the internal reducer must raise an error."""
    from eldermind_core.services.matrix_destiny import _reduce_to_matrix_range

    with pytest.raises(ValueError):
        _reduce_to_matrix_range(0)
