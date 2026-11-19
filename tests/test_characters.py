"""Character lookup, style verdicts and built-in recoveries (integration: real game data)."""
import pytest

from racemech.characters import CharacterMatcher, course_recoveries, load_versions, style_verdict
from racemech.data_sync import cards_path

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def matcher(botlib):
    versions = load_versions(cards_path(botlib.data_dir))
    if not versions:
        pytest.skip("character-cards.json not synced")
    return CharacterMatcher(botlib.game.cards, versions)


@pytest.mark.parametrize("text,card", [
    ("How much stamina should NY Dia have for CM24", 106702),
    ("satono diamond new year", 106702),
    ("jade's prosperity satono diamond", 106702),
    ("og tamamo stamina cm24", 102101),
])
def test_version_resolution(matcher, text, card):
    assert matcher.find(text).card.card_id == card


def test_unnamed_version_is_assumed_and_noted(matcher):
    m = matcher.find("tamamo cross for cm23")
    assert m.version == "Original"
    assert any("assumed" in n for n in m.notes)


def test_style_verdicts(botlib):
    ny_dia = style_verdict(botlib.game.cards[106702], botlib.game.skills)
    assert ny_dia["dominant"] == "late"
    tamamo = style_verdict(botlib.game.cards[102101], botlib.game.skills)
    assert tamamo["dominant"] is None
    assert set(tamamo["candidates"]) == {"pace", "late", "end"}


def test_ny_dia_recoveries_on_long_and_medium(botlib):
    card = botlib.game.cards[106702]
    long_ = {r.name: r for r in course_recoveries(card, botlib.game.skills, 4, "late", {})}
    assert long_["Rain Cloud Bolt"].kind == "unique" and long_["Rain Cloud Bolt"].pct == pytest.approx(0.035)
    assert long_["Stamina Siphon"].status != "no"
    assert "Stamina Eater" not in long_                     # the gold version replaces the white one
    medium = {r.name: r for r in course_recoveries(card, botlib.game.skills, 3, "late", {})}
    assert medium["Stamina Siphon"].status == "no"          # Long races only
