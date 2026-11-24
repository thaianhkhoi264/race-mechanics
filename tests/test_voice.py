"""Code-enforced persona rules (no model needed)."""
from pathlib import Path

import pytest

from racemech.assistant import Persona, _in_voice, _opener, load_persona, tidy_voice, voice_problems

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "persona.example.toml"


def test_no_note_on_bad_news_or_declines():
    assert tidy_voice("I'm afraid I don't have meta data! ♪", "♪") == "I'm afraid I don't have meta data!"
    bad = "520 is not enough, 23 short. Keep going!"
    assert tidy_voice(bad + " ♪", "♪") == bad


def test_at_most_one_note_on_good_news():
    assert tidy_voice("Great skill! ♪ It fits. ♪ Go! ♪", "♪") == "Great skill! ♪ It fits. Go!"
    assert tidy_voice("Plain answer.", "♪") == "Plain answer."
    assert tidy_voice("No note set ♪ ♪", "") == "No note set ♪ ♪"


def test_personas_load_from_files(tmp_path):
    assert load_persona("") is None and load_persona(None) is None
    example = load_persona(EXAMPLE)
    assert "VOICE:" in example.prompt and example.openers and example.bad_news_openers
    with pytest.raises(ValueError):
        load_persona(tmp_path / "missing.toml")


def test_openers_follow_the_verdict():
    p = Persona(openers=("Good question!",), bad_news_openers=("Hm, not quite...",), in_voice=r"^Good\b")
    assert _opener("q", "- VERDICT: enough", p) == "Good question!"
    assert _opener("q", "- VERDICT: does NOT have enough Stamina", p) == "Hm, not quite..."
    assert _opener("q", "anything", Persona()) == ""
    assert _in_voice("Good news, it fits.", p) and not _in_voice("It fits.", p)


CTX = """## Is this Stamina enough? (precomputed verdict)
- Effective Stamina: 595
- VERDICT: effective Stamina 595 vs 556 needed -> enough, 39 to spare.
- RECOMMENDATION: no need to buy a white recovery."""


def test_voice_checks_pass_for_faithful_answer():
    ok = "Good question! You have 595 Stamina against 556 needed, so 39 to spare. ♪"
    assert voice_problems(ok, CTX, "", {"Special Week"}) == []


def test_voice_checks_catch_drops_inventions_and_names():
    dropped = "Good news! Special Week has plenty of Stamina, about 40 extra!"
    problems = voice_problems(dropped, CTX, "", {"Special Week"})
    assert any("dropped key numbers" in p for p in problems)
    assert any("numbers not in the context" in p for p in problems)
    assert any("named characters" in p for p in problems)
