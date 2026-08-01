"""Unit tests for the BaZi (Four Pillars) service, including Da Yun."""

from datetime import date, time

from eldermind_core.services.bazi import compute_bazi


def test_bazi_structure_and_day_master() -> None:
    """BaZi result must contain the four pillars and a Day Master."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30))

    assert "year_pillar" in result
    assert "month_pillar" in result
    assert "day_pillar" in result
    assert "hour_pillar" in result
    assert result["day_master"]["english"] == "Yi"
    assert result["day_master"]["element"] == "Wood"


def test_bazi_element_count_and_useful_god() -> None:
    """Element count and Useful God must be deterministic."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30))

    assert set(result["element_count"].keys()) == {"Wood", "Fire", "Earth", "Metal", "Water"}
    total = sum(result["element_count"].values())
    assert total == 8  # 4 stems + 4 branches

    useful = result["useful_god"]
    assert useful["day_master_strength"] in {"weak", "strong"}
    assert useful["useful_element"] in {"Wood", "Fire", "Earth", "Metal", "Water"}


def test_bazi_ten_gods_present() -> None:
    """Every pillar must expose its Ten Gods relationships."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30))

    for key in ("year_pillar", "month_pillar", "day_pillar", "hour_pillar"):
        pillar = result[key]
        assert "ten_gods" in pillar
        assert "stem_ten_god" in pillar["ten_gods"]
        assert "hidden_stems_ten_gods" in pillar["ten_gods"]


def test_da_yun_forward_for_male_yang_year() -> None:
    """A male born in a Yang year follows the month pillar forward."""
    # 1985 is Yi-Chou (Yin Wood -> Yin year); male + Yin year = backward.
    # Use 1984 Jia-Zi (Yang Wood -> Yang year) for forward.
    result = compute_bazi(date(1984, 6, 15), time(14, 30), gender="male")

    assert result["da_yun_direction"] == "forward"
    assert result["da_yun_start_age"] in {3, 4}
    assert len(result["da_yun"]) == 8

    # Each pillar should span 10 years and the first starts at start_age.
    first = result["da_yun"][0]
    assert first["start_age"] == result["da_yun_start_age"]
    assert first["end_age"] == first["start_age"] + 9

    # Stems and branches should progress forward from the month pillar.
    month_stem = result["month_pillar"]["stem"]["hanzi"]
    month_branch = result["month_pillar"]["branch"]["hanzi"]
    assert result["da_yun"][0]["stem"]["hanzi"] == month_stem
    assert result["da_yun"][0]["branch"]["hanzi"] == month_branch


def test_da_yun_backward_for_female_yang_year() -> None:
    """A female born in a Yang year follows the month pillar backward."""
    result = compute_bazi(date(1984, 6, 15), time(14, 30), gender="female")

    assert result["da_yun_direction"] == "backward"
    assert len(result["da_yun"]) == 8


def test_da_yun_backward_for_male_yin_year() -> None:
    """A male born in a Yin year follows the month pillar backward."""
    # 1985 is Yi-Chou -> Yin year.
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender="male")

    assert result["da_yun_direction"] == "backward"
    assert len(result["da_yun"]) == 8


def test_da_yun_forward_for_female_yin_year() -> None:
    """A female born in a Yin year follows the month pillar forward."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender="female")

    assert result["da_yun_direction"] == "forward"
    assert len(result["da_yun"]) == 8


def test_da_yun_assumed_direction_when_gender_missing() -> None:
    """Without gender, Da Yun falls back to forward with an assumed flag."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender=None)

    assert result["da_yun_direction"] == "forward"
    assert result["da_yun_direction_assumed"] is True
    assert len(result["da_yun"]) == 8


def test_da_yun_direction_not_assumed_when_gender_given() -> None:
    """When gender is provided, direction must not be flagged as assumed."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender="female")

    assert result["da_yun_direction_assumed"] is False


def test_da_yun_pillars_contain_ten_gods() -> None:
    """Each Da Yun pillar must include Ten Gods for interpretation."""
    result = compute_bazi(date(1985, 6, 15), time(14, 30), gender="female")

    for pillar in result["da_yun"]:
        assert "start_age" in pillar
        assert "end_age" in pillar
        assert "stem" in pillar
        assert "branch" in pillar
        assert "ten_gods" in pillar
        assert "stem_ten_god" in pillar["ten_gods"]
