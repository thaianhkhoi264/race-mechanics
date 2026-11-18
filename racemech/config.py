"""
Settings, read from (lowest to highest priority):

1. built-in defaults
2. ``racemech.toml`` in the working directory (gitignored)
3. environment variables ``RACEMECH_<KEY>`` (e.g. ``RACEMECH_MODEL``)
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
    bot_repo: Path = Path(r"<bot_repo path>")
    # Local copies of game data live here (never committed).
    data_dir: Path = REPO_ROOT / "data"
    # Game clients' master databases. Global is the source of truth; JP only fills missing skills.
    global_master: Path = Path(
        r"<path to the Global client>"
        r"\UmamusumePrettyDerby_Data\Persistent\master\master.mdb")
    jp_master: Path = Path(r"<path to the JP client's master.mdb>")
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen3.5:4b-q4_K_M"
    # Seconds to wait for the model before reporting it unavailable.
    timeout_s: float = 120.0
    # How long Ollama keeps the model in VRAM after a request (frees the GPU when idle).
    keep_alive: str = "5m"
    temperature: float = 0.2
    retrieval_k: int = 4


def _coerce(raw, default):
    if isinstance(default, Path):
        return Path(raw)
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
        out[f.name] = default if raw is None else _coerce(raw, default)
    return Settings(**out)
