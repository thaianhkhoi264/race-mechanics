"""Entity extraction and retrieval (CI-safe: synthetic skills, shipped knowledge pack only)."""
from dataclasses import dataclass

import pytest

from racemech.entities import SkillMatcher, extract
from racemech.retrieval import build_index, tokenize


@dataclass
class FakeSkill:
    name: str
    source: str = "global"


SKILLS = {
    "100511": FakeSkill("Budding Blossom"),
    "900511": FakeSkill("Budding Blossom"),
    "100591": FakeSkill("Moving Past, and Beyond"),
    "200011": FakeSkill("Right-Handed ◎"),
    "200012": FakeSkill("Right-Handed ○"),
    "200013": FakeSkill("Right-Handed ×"),
    "201601": FakeSkill("Groundwork"),
    "202451": FakeSkill("Pedal to the Metal"),
    "200031": FakeSkill("Tokyo Racecourse ◎"),
    "200032": FakeSkill("Tokyo Racecourse ○"),
    "200131": FakeSkill("Standard Distance ◎"),
    "200132": FakeSkill("Standard Distance ○"),
    "200142": FakeSkill("Non-Standard Distance ○"),
    "200891": FakeSkill("Subdued Late Surgers"),
    "200861": FakeSkill("Subdued Pace Chasers"),
    "200601": FakeSkill("On Your Left!"),
    "999999": FakeSkill("新スキル", source="jp"),
}


@pytest.fixture(scope="module")
def matcher():
    return SkillMatcher(SKILLS)


def test_typo_tolerant_skill_match(matcher):
    e = extract("what does budding blosom do on CM21", matcher)
    assert [s.sid for s in e.skills] == ["100511"]
    assert e.cm == 21


def test_punctuation_and_tier_default(matcher):
    e = extract("moving past and beyond vs right handed", matcher)
    assert {s.sid for s in e.skills} == {"100591", "200012"}     # ○ by default, never ×
    assert any("○" in n for n in e.notes)


def test_tier_as_written(matcher):
    assert extract("Right-Handed ◎ worth it?", matcher).skills[0].sid == "200011"


@pytest.mark.parametrize("text,sid", [
    ("is pttm good", "202451"), ("PTTM?", "202451"), ("should i get pedal", "202451"),
    ("oyl on cm21", "200601"), ("kanata", "100591"), ("gw for front", "201601"),
])
def test_shorthand(matcher, text, sid):
    assert sid in {s.sid for s in extract(text, matcher).skills}


def test_user_example(matcher):
    q = ("A late surger with 515 stamina in CM 22, has tokyo and standard distance. "
         "Should I buy a white recovery skill? Will the uma survive 2 subdued debuff skill?")
    e = extract(q, matcher)
    by_sid = {s.sid: s for s in e.skills}
    assert {"200032", "200132", "200891"} <= set(by_sid)        # ○ greens, style-matched debuff
    assert "200142" not in by_sid                               # not Non-Standard Distance
    assert by_sid["200891"].count == 2
    assert e.recoveries == [] and e.candidate_recoveries == pytest.approx([0.015])
    assert e.stamina == 515 and e.styles == ["late"] and e.cm == 22


def test_venue_alone_is_not_a_skill(matcher):
    assert not extract("what is the best skill in tokyo", matcher).skills


def test_inherited_maps_to_9_id(matcher):
    e = extract("is inherited Budding Blossom good", matcher)
    assert e.skills[0].sid == "900511"


def test_jp_only_names_are_not_fuzzy_matched(matcher):
    assert "999999" not in {s.sid for s in extract("新スキル", matcher).skills}


@pytest.mark.parametrize("text,expected,noted", [
    ("late surger with 770 stamina and 0.35 recovery", [0.035], True),
    ("with a 3.5% recovery", [0.035], False),
    ("plus 0.035 heal", [0.035], False),
    ("how much is a white recovery worth", [0.015], False),
])
def test_recovery_parsing(text, expected, noted):
    e = extract(text)
    assert e.recoveries == pytest.approx(expected)
    assert bool(e.notes) is noted


def test_style_stamina_debuffers():
    e = extract("End Closer, 900 stam, vs 2 debuffers")
    assert e.styles == ["end"] and e.stamina == 900 and e.debuffers == 2


def test_pace_chaser_is_not_end_closer():
    assert extract("is it good for a pace chaser").styles == ["pace"]


def test_aliases_in_tokenizer():
    assert "acceleration" in tokenize("accel") and "speed" in tokenize("velocity")


@pytest.mark.parametrize("question,title_word", [
    ("are velocity and accel skills additive or multiplicative", "additive"),
    ("how does downhill accel mode work", "downhill"),
    ("how many seconds does a skill last on 2500m", "duration"),
    ("what is guts used for", "guts"),
])
def test_retrieval_finds_the_right_section(question, title_word):
    hits = build_index().search(question, 3)
    assert any(title_word in d.title.lower() for _, d in hits)


@pytest.mark.parametrize("text,wit,power", [
    ("late surger 900 wit cm22, how much does wit help", 900, None),
    ("is 750 power enough for cm19", None, 750),
    ("wit 1100 pow 1000 pace chaser", 1100, 1000),
    ("what does wit do in cm21", None, None),
])
def test_wit_and_power_values(text, wit, power):
    e = extract(text)
    assert e.wit == wit
    assert e.power == power
