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
