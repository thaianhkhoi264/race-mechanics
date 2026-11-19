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


def test_downhill_gain():
    hill = [{"start": 100, "length": 775, "slope": -10000}]       # CM21's 1% downhill
    assert stats.downhill_boost(-10000) == pytest.approx(0.4)
    assert stats.downhill_gain_m(hill, 1200, 20.8) == pytest.approx(775 / 20.8 * 0.48 / 0.68 * 0.4)


def test_speed_carryover():
    # 2500 m: base speed 19.5, late-race at 1,666.7 m; +0.35 for baseDuration 40000 -> 10 s
    c = stats.speed_carryover(1525, 40000, 2500, 0.35)
    assert c["duration_s"] == pytest.approx(10.0)
    assert c["end_m"] == pytest.approx(1525 + 19.85 * 10)
    assert c["carry_m"] == pytest.approx(1723.5 - 2500 * 2 / 3)
    early = stats.speed_carryover(1000, 40000, 2500, 0.35)
    assert early["carry_m"] == 0 and early["short_m"] == pytest.approx(2500 * 2 / 3 - 1198.5)
