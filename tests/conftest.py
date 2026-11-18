import pytest

from racemech.botlib import BotLib, BotLibError
from racemech.config import load_settings


@pytest.fixture(scope="session")
def botlib():
    """Real bot modules + synced data; integration tests skip when unavailable."""
    s = load_settings()
    try:
        return BotLib(s.bot_repo, s.data_dir).load()
    except BotLibError as exc:
        pytest.skip(f"integration setup unavailable: {exc}")


@pytest.fixture(scope="session")
def cm22(botlib):
    c = botlib.course_for_cm(22)
    if c is None:
        pytest.skip("CM22 not in the live timeline")
    return c


@pytest.fixture(scope="session")
def cm21(botlib):
    c = botlib.course_for_cm(21)
    if c is None:
        pytest.skip("CM21 not in the live timeline")
    return c
