"""
Settings, read from (lowest to highest priority):

1. built-in defaults
2. ``racemech.toml`` in the working directory (gitignored)
3. environment variables ``RACEMECH_<KEY>`` (e.g. ``RACEMECH_MODEL``)

Nothing machine-specific is built in: the ``bot_repo`` codebase, the game databases and the
data sources stay unset until ``racemech.toml`` or the environment provides them (see
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
    # Read-only path to the codebase whose calculator modules are reused.
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
    # Online sources for `racemech sync`; each one left empty is skipped (see data_sync.py).
    # Course geometry JSON, keyed by course id.
    course_data_url: str = ""
    # Upcoming-events timeline JSON (optionally gzipped), for CMs not in the game data yet.
    cm_timeline_url: str = ""
    # Where `racemech sync` copies character-cards.json from (scp host:path or a local path).
    # If that fails, it downloads the file via the manifest ("character-cards" -> hash) and the
    # data URL template with {name} and {hash} fields.
    cards_source: str = ""
    cards_manifest_url: str = ""
    cards_data_url: str = ""
    # Where `racemech sync` copies CM simulation snapshots from (scp host:path). If that fails, it
    # fetches them with this module of the bot_repo codebase, which also reads them.
    sim_source: str = ""
    sim_module: str = ""
    # Answer persona: path to a persona TOML file (see docs/persona.example.toml); "" = plain.
    voice: str = ""
    # Model context window in tokens.
    num_ctx: int = 16384
    # `racemech serve` (a calling application asks questions over HTTP). The token is a shared
    # secret sent as "Authorization: Bearer <token>"; the server won't start without one.
    serve_host: str = "0.0.0.0"
    serve_port: int = 8000
    serve_token: str = ""
    serve_max_waiting: int = 3
    serve_voice: str = ""


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
