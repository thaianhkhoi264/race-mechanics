"""
Settings, read from (lowest to highest priority):

1. built-in defaults
2. ``racemech.toml`` in the working directory (gitignored)
3. environment variables ``RACEMECH_<KEY>`` (e.g. ``RACEMECH_MODEL``)

Nothing machine-specific is built in: the bot_repo checkout, the game databases and the
copy sources stay unset until ``racemech.toml`` or the environment provides them (see
``racemech.example.toml``). Commands that need one say which setting is missing.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    # Read-only path to a bot_repo checkout whose calculator modules are reused.
    bot_repo: Path | None = None
    # Local copies of game data live here (never committed).
    data_dir: Path = REPO_ROOT / "data"
    # Game clients' master databases. Global is the source of truth; JP only fills missing skills.
    global_master: Path | None = None
    jp_master: Path | None = None
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen3.5:9b-q4_K_M"
    # Seconds to wait for the model before reporting it unavailable.
    timeout_s: float = 120.0
    # How long Ollama keeps the model in VRAM after a request (frees the GPU when idle).
    keep_alive: str = "5m"
    temperature: float = 0.2
    retrieval_k: int = 5
    # Put the whole race mechanics doc in the system prompt (a fixed prefix Ollama can reuse)
    # instead of retrieving mechanics sections per question.
    full_mechanics: bool = True
    # Where `racemech sync` copies the character database's character-cards.json from (scp host:path or a local
    # path), e.g. a copy a scraper keeps current. Empty: download it from the character database.
    cards_source: str = ""
    # Answer voice: "" (plain) or "persona" (see racemech/prompts/voice_persona.md).
    voice: str = ""
    # Where `racemech sync` copies simulation CM simulation snapshots from (scp host:path), e.g. where
    # bot_repo saves them daily. Empty: fetch directly with the bot's sim_module.
    sim_source: str = ""
    # Model context window in tokens.
    num_ctx: int = 16384
    # `racemech serve` (bot_repo asks questions over the LAN). The token is a shared secret
    # the bot sends as "Authorization: Bearer <token>"; the server won't start without one.
    serve_host: str = "0.0.0.0"
    serve_port: int = 8000
    serve_token: str = ""
    serve_max_waiting: int = 3
    serve_voice: str = "persona"


def _coerce(raw, default, type_name: str = ""):
    if isinstance(default, Path) or (default is None and "Path" in type_name):
        return Path(raw) if str(raw).strip() else None
    if isinstance(default, bool):
        return raw if isinstance(raw, bool) else str(raw).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, float):
        return float(raw)
    if isinstance(default, int):
        return int(raw)
    return str(raw)


def load_settings(config_path: Path | None = None) -> Settings:
    values: dict = {}
    path = config_path or Path.cwd() / "racemech.toml"
    if path.is_file():
        with path.open("rb") as f:
            values.update(tomllib.load(f))
    defaults = Settings()
    out = {}
    for f in fields(Settings):
        default = getattr(defaults, f.name)
        raw = os.environ.get(f"RACEMECH_{f.name.upper()}", values.get(f.name))
        out[f.name] = default if raw is None else _coerce(raw, default, str(f.type))
    return Settings(**out)
