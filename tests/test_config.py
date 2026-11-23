from pathlib import Path

from racemech.config import Settings, load_settings


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.delenv("RACEMECH_MODEL", raising=False)
    s = load_settings(tmp_path / "missing.toml")
    assert s == Settings()


def test_file_then_env_override(tmp_path, monkeypatch):
    cfg = tmp_path / "racemech.toml"
    cfg.write_text('model = "from-file"\ntimeout_s = 30\nbot_repo = "X:/bot"\n', encoding="utf-8")
    monkeypatch.setenv("RACEMECH_MODEL", "from-env")
    s = load_settings(cfg)
    assert s.model == "from-env"
    assert s.timeout_s == 30.0
    assert s.bot_repo == Path("X:/bot")


def test_nothing_machine_specific_is_built_in(tmp_path, monkeypatch):
    for key in ("BOT_REPO", "GLOBAL_MASTER", "JP_MASTER", "CARDS_SOURCE", "SIM_SOURCE"):
        monkeypatch.delenv(f"RACEMECH_{key}", raising=False)
    s = load_settings(tmp_path / "missing.toml")
    assert s.bot_repo is None and s.global_master is None and s.jp_master is None
    assert s.cards_source == "" and s.sim_source == ""


def test_path_settings_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RACEMECH_BOT_REPO", "X:/bot")
    monkeypatch.setenv("RACEMECH_JP_MASTER", "")
    s = load_settings(tmp_path / "missing.toml")
    assert s.bot_repo == Path("X:/bot") and s.jp_master is None
