"""Stat formulas checked against the values quoted in the race mechanics notes."""
import pytest

from racemech import stats


@pytest.mark.parametrize("wit,pct", [(300, 70.0), (600, 85.0), (900, 90.0), (1200, 92.5), (100, 20.0)])
def test_skill_activation(wit, pct):
    assert stats.skill_activation_pct(wit) == pytest.approx(pct)


@pytest.mark.parametrize("wit,pct", [(300, 19), (600, 14), (900, 12), (1200, 10)])
def test_rushed_rounded_up(wit, pct):
    assert stats.rushed_pct(wit) == pct


@pytest.mark.parametrize("wit,lo,hi", [(400, -0.533, 0.117), (800, -0.373, 0.277)])
def test_section_random(wit, lo, hi):
    got_lo, got_hi = stats.section_random_pct(wit)
    assert got_lo == pytest.approx(lo, abs=0.001)
    assert got_hi == pytest.approx(hi, abs=0.001)


def test_downhill_share_and_uphill_loss():
    assert stats.downhill_mode_share(1000) == pytest.approx(0.4 / 0.6)
    assert stats.uphill_loss(20000, 1000) == pytest.approx(0.4)      # 2% grade
    assert stats.base_speed(1600) == pytest.approx(20.4)
