"""Code-enforced voice rules (no model needed)."""
import pytest

from racemech.assistant import tidy_voice, voice_prompt


def test_no_note_on_bad_news_or_declines():
    assert tidy_voice("I'm afraid I don't have meta data! ♪") == "I'm afraid I don't have meta data!"
    bad = "520 is not enough, 23 short. Keep going!"
    assert tidy_voice(bad + " ♪") == bad


def test_at_most_one_note_on_good_news():
    assert tidy_voice("Great skill! ♪ It fits. ♪ Go! ♪") == "Great skill! ♪ It fits. Go!"
    assert tidy_voice("Plain answer.") == "Plain answer."


def test_voice_prompts():
    assert voice_prompt("") == ""
    assert "VOICE:" in voice_prompt("persona")
    with pytest.raises(ValueError):
        voice_prompt("nobody")


CTX = """## Is this Stamina enough? (precomputed verdict)
- Effective Stamina: 595
- VERDICT: effective Stamina 595 vs 556 needed -> enough, 39 to spare.
- RECOMMENDATION: no need to buy a white recovery."""


def test_voice_checks_pass_for_faithful_answer():
    from racemech.assistant import voice_problems
    ok = "Of course, Trainer! You have 595 Stamina against 556 needed, so 39 to spare. ♪"
    assert voice_problems(ok, CTX, "", {"Satono Diamond"}) == []


def test_voice_checks_catch_drops_inventions_and_names():
    from racemech.assistant import voice_problems
    dropped = "Hehe! Satono Diamond has plenty of Stamina, about 40 extra!"
    problems = voice_problems(dropped, CTX, "", {"Satono Diamond"})
    assert any("dropped key numbers" in p for p in problems)
    assert any("numbers not in the context" in p for p in problems)
    assert any("named characters" in p for p in problems)
