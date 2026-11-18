"""Announced/predicted CMs come from the cached events timeline when the game data lacks them."""
import pytest

pytestmark = pytest.mark.integration


def test_released_cm_prefers_game_data(botlib, cm22):
    assert cm22.predicted is False and cm22.note is None


def test_unreleased_cm_falls_back_to_timeline(botlib):
    future = [n for n in sorted(botlib.timeline) if n not in botlib.game.champions]
    if not future:
        pytest.skip("no cached timeline with unreleased CMs (run `racemech sync`)")
    c = botlib.course_for_cm(future[0])
    assert c is not None and c.entry["distance"] > 0
    assert c.note and f"CM#{future[0]}" in c.note
    assert c.predicted == ("Predicted" in c.display)
