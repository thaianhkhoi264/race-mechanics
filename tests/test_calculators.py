"""Golden values worked out by hand in the design discussion, reproduced through the calculators."""
import pytest

from racemech import calculators as calc

pytestmark = pytest.mark.integration


def test_white_recovery_equivalent_cm22(botlib, cm22):
    f = calc.recovery_equivalent(botlib, cm22, 0.015)
    assert f.data["front"] == pytest.approx(39.1, abs=0.5)
    assert f.data["pace"] == pytest.approx(42.4, abs=0.5)
    assert f.data["late"] == pytest.approx(38.1, abs=0.5)
    assert f.data["end"] == pytest.approx(38.5, abs=0.5)


def test_debuffers_late_770_with_3_5_recovery_cm22(botlib, cm22):
    f = calc.survivable_debuffers(botlib, cm22, 770, "late", recoveries=(0.035,))
    assert f.data["pair"] == pytest.approx(3.28, abs=0.03)
    assert f.data["gold"] == pytest.approx(4.49, abs=0.03)


def test_debuffers_without_recovery_cm22(botlib, cm22):
    f = calc.survivable_debuffers(botlib, cm22, 770, "late")
    assert f.data["pair"] == pytest.approx(2.30, abs=0.03)


def test_baseline_late_cm22(botlib, cm22):
    f = calc.stamina_baseline(botlib, cm22, styles=("late",))
    assert f.data["late"] == pytest.approx(543.3, abs=0.5)


def test_skill_on_course_moving_past_cm21(botlib, cm21):
    f = calc.skill_on_course(botlib, "100591", cm21)
    text = f.render()
    assert "550–788 m" in text
    assert "5th–6th" in text
    assert "Decent accel" in text


def test_wit_on_cm21_downhill_savings(botlib, cm21):
    f = calc.wit_on_course(botlib, cm21, styles=("late",))
    assert f.data["downhill_m"] == 775
    assert f.data["pk_end"] == pytest.approx(500)
    assert f.data["levels"][1200.0]["rushed"] == 10
    assert any("Late Surger downhill HP saved" in ln for ln in f.lines)


def test_power_on_cm22_uphill(botlib, cm22):
    f = calc.power_on_course(botlib, cm22, power=1000)
    assert f.data["uphill_m"] == 250
    assert f.data["levels"][1000.0] == pytest.approx(3.7, abs=0.1)
    assert 1200.0 in f.data["levels"]


def test_wit_summary_cm21_sprint(botlib, cm21):
    f = calc.wit_on_course(botlib, cm21)
    assert f.data["gain_m"][1200.0] == pytest.approx(10.5, abs=0.2)
    assert "matters a lot" in f.data["summary"]
    assert "not a concern" in f.data["summary"]


def test_to_the_finish_wording():
    out = calc._clear_activates("On the final straight (1,099–1,600 m to the finish) — if you're 2nd")
    assert out == ("On the final straight (from the 1,099 m mark to the finish line at 1,600 m)"
                   " — if you're 2nd")


def test_course_layout_cm22(cm22):
    f = calc.course_layout(cm22)
    assert f.data["p1"] == pytest.approx(266.7, abs=0.1)
    assert f.data["p2"] == pytest.approx(1066.7, abs=0.1)
    assert any(ln.startswith("Final straight:") for ln in f.lines)
