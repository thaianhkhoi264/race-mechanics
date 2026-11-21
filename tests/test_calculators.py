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
    assert "WAITS FOR RACE STATE" in text and "550 m (mid-race) to 788 m" in text
    assert "OVERALL RATING" not in text          # the LLM judges skills itself now


def test_when_it_fires_lines():
    state = calc.when_it_fires({"trigger_kind": "state", "window": (1067, 1600)}, 1600)
    assert "WAITS FOR RACE STATE" in state and "1,067 m (late-race) to the finish" in state
    fixed = calc.when_it_fires({"trigger_kind": "fixed", "window": (1067, 1200)}, 1600)
    assert "FIXED POINT" in fixed and "starts at 1,067 m" in fixed
    rnd = calc.when_it_fires({"trigger_kind": "random", "window": (1667, 1875)}, 2500)
    assert "RANDOM POINT" in rnd and "about 1,771 m (104 m after late-race starts)" in rnd
    assert calc.when_it_fires({"trigger_kind": None, "window": None}, 1600) is None


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


def test_drain_skill_counts_as_recovery_not_debuff(botlib):
    from racemech.context import ContextBuilder
    from racemech.retrieval import build_index
    cb = ContextBuilder(botlib, build_index(), 5)
    ctx = cb.build("late surger 1000 stam with stamina siphon cm20, enough?")       # CM20 is Long
    plan = next(f for f in ctx.facts if f.title.startswith("Is this Stamina enough"))
    text = "\n".join(plan.lines)
    assert "Debuffs expected: none" in text and "1 x Stamina Siphon (3.5%)" in text
    assert not any(f.title.startswith("Course layout") for f in ctx.facts)    # "late surger" is not a phase
    mile = cb.build("late surger 1000 stam with stamina siphon cm22, enough?")    # Long-only skill
    assert any("Stamina Siphon does not activate" in n for n in mile.notes)


def test_speed_carryover_line(botlib):
    cm20 = botlib.course_for_cm(20)
    def carry(sid):
        lines = calc.skill_on_course(botlib, sid, cm20).lines
        return [ln for ln in lines if ln.startswith("SPEED CARRYOVER")]
    fixed = carry("110081")
    assert fixed and "fires at 1,525 m" in fixed[0] and "first 57 m (2.9 s) of late-race" in fixed[0]
    state = carry("10071")
    assert state and "only if it fires after about 1,372 m" in state[0]
