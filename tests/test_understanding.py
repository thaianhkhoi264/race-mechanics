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
    "999999": FakeSkill("新スキル", source="jp"),
}


@pytest.fixture(scope="module")
def matcher():
    return SkillMatcher(SKILLS)


def test_typo_tolerant_skill_match(matcher):
    e = extract("what does budding blosom do on CM21", matcher)
    assert [s.sid for s in e.skills] == ["100511"]
    assert e.cm == 21


def test_punctuation_and_tier_preference(matcher):
    e = extract("moving past and beyond vs right handed", matcher)
    assert {s.sid for s in e.skills} == {"100591", "200011"}     # ◎ preferred, never ×


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
