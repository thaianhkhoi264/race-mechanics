"""
Refresh this project's local data.

1. Copy the game clients' ``master.mdb`` databases (Global, and JP if installed) into
   ``<data_dir>/game/``. Copies mean a running or patching game is never touched; this
   is the source of skills, names, track names and the released Champions Meeting list.
2. Download course geometry (corners, straights, slopes) from community skill data. The game
   keeps geometry in asset bundles, not in master.mdb; the file is cached and only changes
   when new racecourses are added.
3. Download the events timeline (the same one bot_repo reads), cached locally, for
   Champions Meetings that are announced or predicted but not in the Global game data yet.
4. Copy the character database's ``character-cards.json`` (version tags such as ``new_year``) from the remote host,
   where a scraper saves it; if the remote host can't be reached, download it from
   the character database directly (manifest -> hashed data file); if both fail, keep the previous copy.

5. Copy the simulations' CM simulation snapshots (``data/simulations/``) from the remote host, where
   the bot_repo codebase's ``sim_module`` saves them daily; if the remote host can't be reached, fetch new
   snapshots directly with that same module (imported read-only from the bot checkout).

Answering questions never goes online; it only reads these cached files.
"""
from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from racemech.gamedata import game_dir

COURSE_DATA_URL = "<course data URL>"
CM_TIMELINE_URL = "<events timeline URL>"


CARDS_MANIFEST_URL = "<character database manifest URL>"
CARDS_DATA_URL = "<character database data URL>"


def cards_path(data_dir: Path) -> Path:
    return data_dir / "character-cards.json"


def _valid_cards(body: bytes) -> bool:
    try:
        data = json.loads(body)
    except ValueError:
        return False
    return isinstance(data, list) and bool(data) and "card_id" in data[0]


def _cards_from_source(source: str, timeout: float) -> bytes | None:
    """``host:/path`` is copied with scp (key auth only, no prompts); a plain path is read."""
    if not source:
        return None
    local = Path(source)
    if local.is_file():
        return local.read_bytes()
    if ":" not in source or (len(source) > 1 and source[1] == ":"):     # a drive letter, not host:path
        return None
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = Path(f.name)
    try:
        r = subprocess.run(["scp", "-q", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={int(timeout)}",
                            source, str(tmp)], capture_output=True, timeout=timeout + 30)
        return tmp.read_bytes() if r.returncode == 0 and tmp.is_file() else None
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        tmp.unlink(missing_ok=True)


def _cards_from_download(timeout: float) -> bytes | None:
    req = lambda url: urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (racemech)"})  # noqa: E731
    try:
        with urllib.request.urlopen(req(CARDS_MANIFEST_URL), timeout=timeout) as resp:
            manifest = json.loads(resp.read())
        url = CARDS_DATA_URL.format(name="character-cards", hash=manifest["character-cards"])
        with urllib.request.urlopen(req(url), timeout=timeout) as resp:
            return resp.read()
    except (OSError, ValueError, KeyError):
        return None


def sync_cards(data_dir: Path, source: str, timeout: float = 60.0) -> str:
    for label, body in (("copied from " + source, lambda: _cards_from_source(source, timeout)),
                        ("downloaded from the character database", lambda: _cards_from_download(timeout))):
        raw = body()
        if raw and _valid_cards(raw):
            _write_atomic(cards_path(data_dir), raw)
            return f"{len(json.loads(raw))} cards ({label})"
    if cards_path(data_dir).is_file():
        return "kept the previous copy (remote host and the character database unreachable)"
    return "missing (remote host and the character database unreachable); character versions unavailable"


def sim_dir(data_dir: Path) -> Path:
    return data_dir / "simulation"


def sync_simulations(data_dir: Path, source: str, bot_repo: Path | None, timeout: float = 60.0) -> str:
    dest = sim_dir(data_dir)
    if source and ":" in source and not (len(source) > 1 and source[1] == ":"):
        try:
            cmd = ["scp", "-q", "-r", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={int(timeout)}",
                   source.rstrip("/"), str(data_dir)]
            r = subprocess.run(cmd, capture_output=True, timeout=timeout * 20)
            if r.returncode == 0 and dest.is_dir():
                return f"copied from {source}"
        except (OSError, subprocess.TimeoutExpired):
            pass
    if bot_repo is not None and (Path(bot_repo) / "sim_module.py").is_file():
        import importlib
        import sys
        if str(bot_repo) not in sys.path:
            sys.path.insert(0, str(bot_repo))
        try:
            new = importlib.import_module("sim_module").sync(dest)
            return f"fetched from simulation directly ({len(new)} new snapshots)"
        except Exception as exc:  # noqa: BLE001 - any network/site failure keeps the old copy
            return f"kept the previous copy (remote host unreachable, simulation fetch failed: {exc})"
    return "kept the previous copy (remote host unreachable)" if dest.is_dir() else "missing (remote host unreachable)"


def cm_timeline_path(data_dir: Path) -> Path:
    return data_dir / "cm_timeline.json"


def _write_atomic(dest: Path, body: bytes) -> None:
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(body)
    tmp.replace(dest)


def course_data_path(data_dir: Path) -> Path:
    return data_dir / "course_data.json"


def _atomic_copy(src: Path, dest: Path) -> int:
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    shutil.copyfile(src, tmp)
    tmp.replace(dest)
    return dest.stat().st_size


def sync(data_dir: Path, global_master: Path, jp_master: Path | None,
         download_courses: bool = True, timeout: float = 60.0,
         cards_source: str = "", sim_source: str = "",
         bot_repo: Path | None = None) -> list[tuple[str, str]]:
    """Returns (item, status) lines."""
    out: list[tuple[str, str]] = []
    gd = game_dir(data_dir)
    gd.mkdir(parents=True, exist_ok=True)

    if not global_master.is_file():
        raise FileNotFoundError(f"Global master.mdb not found at {global_master}")
    out.append(("global_master.mdb", f"{_atomic_copy(global_master, gd / 'global_master.mdb'):,} bytes"))
    if jp_master and jp_master.is_file():
        out.append(("jp_master.mdb", f"{_atomic_copy(jp_master, gd / 'jp_master.mdb'):,} bytes"))
    else:
        out.append(("jp_master.mdb", "skipped (JP client not found)"))

    if download_courses:
        dest = course_data_path(data_dir)
        with urllib.request.urlopen(COURSE_DATA_URL, timeout=timeout) as resp:
            body = resp.read()
        tmp = dest.with_suffix(".json.tmp")
        tmp.write_bytes(body)
        tmp.replace(dest)
        out.append(("course_data.json", f"{len(body):,} bytes (downloaded)"))

        req = urllib.request.Request(CM_TIMELINE_URL, headers={"User-Agent": "racemech"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass                       # served already decompressed
        _write_atomic(cm_timeline_path(data_dir), raw)
        out.append(("cm_timeline.json", f"{len(raw):,} bytes (downloaded)"))
        out.append(("character-cards.json", sync_cards(data_dir, cards_source, timeout)))
        out.append(("simulation/", sync_simulations(data_dir, sim_source, bot_repo, timeout)))
    return out
