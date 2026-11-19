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
