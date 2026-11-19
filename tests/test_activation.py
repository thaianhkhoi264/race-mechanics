"""Why a skill can't activate here (integration: real skills and courses)."""
import pytest

from racemech import calculators as calc

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("sid,expect", [
    ("200062", "only at Kyoto; this course is Tokyo"),                       # Kyoto Racecourse ○
    ("200012", "only on right-handed (clockwise) courses"),                  # Right-Handed ○
])
def test_cannot_activate_reasons_cm22(botlib, cm22, sid, expect):
    f = calc.skill_on_course(botlib, sid, cm22)
    assert any(ln.startswith("CANNOT ACTIVATE") and expect in ln for ln in f.lines)


def test_style_mismatch(botlib):
    cm20 = botlib.course_for_cm(20)
    f = calc.skill_on_course(botlib, "202421", cm20, "front")              # Claw Forward: Late Surger only
    assert any(ln.startswith("STYLE MISMATCH") for ln in f.lines)
    assert any("USELESS" in ln for ln in f.lines)
    ok = calc.skill_on_course(botlib, "202421", cm20, "late")
    assert not any(ln.startswith("STYLE MISMATCH") for ln in ok.lines)


def test_clear_effect():
    assert calc.clear_effect("HP Recovery +0.055") == "restores 5.5% of max HP"
    assert calc.clear_effect("Acceleration +0.4, HP Recovery -0.02 for 3.8 s") == \
        "Acceleration +0.4, costs 2% of max HP for 3.8 s"
    assert calc.clear_effect("HP Recovery +0.035, HP Recovery -0.01 on other runners") == \
        "restores 3.5% of max HP, drains 1% of max HP from other runners"
