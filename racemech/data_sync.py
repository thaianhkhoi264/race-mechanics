"""
Refresh this project's local data. Every online source is a setting (see
``racemech.example.toml``); a source that isn't set is skipped and reported, and the previous
copy is kept.

1. Copy the game clients' ``master.mdb`` databases (Global, and JP if installed) into
   ``<data_dir>/game/``. Copies mean a running or patching game is never touched; this
   is the source of skills, names, track names and the released Champions Meeting list.
2. Download course geometry (corners, straights, slopes) from ``course_data_url``. The game
   keeps geometry in asset bundles, not in master.mdb; the file is cached and only changes
   when new racecourses are added.
3. Download an upcoming-events timeline from ``cm_timeline_url`` (optionally gzipped), cached
   locally, for Champions Meetings that are announced or predicted but not in the Global game
   data yet.
4. Copy the character version data (``character-cards.json``, version tags such as
   ``new_year``) from ``cards_source``; if that fails, download it via ``cards_manifest_url`` /
   ``cards_data_url``; if both fail, keep the previous copy.
5. Copy CM simulation snapshots into ``data/simulations/`` from ``sim_source``; if that fails,
   fetch new snapshots with the ``sim_module`` of the ``bot_repo`` codebase (imported
   read-only).

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


def cards_path(data_dir: Path) -> Path:
    return data_dir / "character-cards.json"


def _valid_cards(body: bytes) -> bool:
    try:
        data = json.loads(body)
    except ValueError:
        return False
    return isinstance(data, list) and bool(data) and "card_id" in data[0]


def _is_remote(source: str) -> bool:
    """``host:path`` (copied with scp), as opposed to a local path with a drive letter."""
    return ":" in source and not (len(source) > 1 and source[1] == ":")


def _cards_from_source(source: str, timeout: float) -> bytes | None:
    """``host:/path`` is copied with scp (key auth only, no prompts); a plain path is read."""
    if not source:
        return None
    local = Path(source)
    if local.is_file():
        return local.read_bytes()
    if not _is_remote(source):
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


def _cards_from_download(manifest_url: str, data_url: str, timeout: float) -> bytes | None:
    """The manifest maps "character-cards" to a hash; ``data_url`` has {name} and {hash} fields."""
    if not (manifest_url and data_url):
        return None
    req = lambda url: urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (racemech)"})  # noqa: E731
    try:
        with urllib.request.urlopen(req(manifest_url), timeout=timeout) as resp:
            manifest = json.loads(resp.read())
        url = data_url.format(name="character-cards", hash=manifest["character-cards"])
        with urllib.request.urlopen(req(url), timeout=timeout) as resp:
            return resp.read()
    except (OSError, ValueError, KeyError):
        return None


def sync_cards(data_dir: Path, source: str, manifest_url: str = "", data_url: str = "",
               timeout: float = 60.0) -> str:
    if not source and not (manifest_url and data_url):
        if cards_path(data_dir).is_file():
            return "kept the previous copy (cards_source and cards_manifest_url not set)"
        return "skipped (cards_source and cards_manifest_url not set); character versions unavailable"
    for label, body in (("copied from " + source, lambda: _cards_from_source(source, timeout)),
                        ("downloaded", lambda: _cards_from_download(manifest_url, data_url, timeout))):
        raw = body()
        if raw and _valid_cards(raw):
            _write_atomic(cards_path(data_dir), raw)
            return f"{len(json.loads(raw))} cards ({label})"
    if cards_path(data_dir).is_file():
        return "kept the previous copy (copy source and download both unavailable)"
    return "missing (copy source and download both unavailable); character versions unavailable"


def sim_dir(data_dir: Path) -> Path:
    return data_dir / "simulations"


def sync_simulations(data_dir: Path, source: str, bot_repo: Path | None, module: str,
                     timeout: float = 60.0) -> str:
    dest = sim_dir(data_dir)
    if source and _is_remote(source):
        tmp = data_dir / "simulations.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            cmd = ["scp", "-q", "-r", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={int(timeout)}",
                   source.rstrip("/"), str(tmp)]
            r = subprocess.run(cmd, capture_output=True, timeout=timeout * 20)
            if r.returncode == 0 and tmp.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
                tmp.replace(dest)
                return f"copied from {source}"
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if module and bot_repo is not None and (Path(bot_repo) / f"{module}.py").is_file():
        import importlib
        import sys
        if str(bot_repo) not in sys.path:
            sys.path.insert(0, str(bot_repo))
        try:
            new = importlib.import_module(module).sync(dest)
            return f"fetched directly ({len(new)} new snapshots)"
        except Exception as exc:  # noqa: BLE001 - any network/site failure keeps the old copy
            return f"kept the previous copy (copy failed, direct fetch failed: {exc})"
    why = "sim_source and sim_module not set" if not source and not module else "copy source unreachable"
    return f"kept the previous copy ({why})" if dest.is_dir() else f"missing ({why})"


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


def _download(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "racemech"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def sync(data_dir: Path, global_master: Path | None, jp_master: Path | None,
         download_courses: bool = True, timeout: float = 60.0,
         cards_source: str = "", sim_source: str = "",
         bot_repo: Path | None = None, *, course_data_url: str = "", cm_timeline_url: str = "",
         cards_manifest_url: str = "", cards_data_url: str = "",
         sim_module: str = "") -> list[tuple[str, str]]:
    """Returns (item, status) lines."""
    if global_master is None:
        raise FileNotFoundError("global_master is not set: point it at the Global client's master.mdb "
                                "in racemech.toml or RACEMECH_GLOBAL_MASTER")
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
        if course_data_url:
            body = _download(course_data_url, timeout)
            _write_atomic(course_data_path(data_dir), body)
            out.append(("course_data.json", f"{len(body):,} bytes (downloaded)"))
        else:
            out.append(("course_data.json", "skipped (course_data_url not set)"))

        if cm_timeline_url:
            raw = _download(cm_timeline_url, timeout)
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass                       # served already decompressed
            _write_atomic(cm_timeline_path(data_dir), raw)
            out.append(("cm_timeline.json", f"{len(raw):,} bytes (downloaded)"))
        else:
            out.append(("cm_timeline.json", "skipped (cm_timeline_url not set)"))
        out.append(("character-cards.json",
                    sync_cards(data_dir, cards_source, cards_manifest_url, cards_data_url, timeout)))
        out.append(("simulations/", sync_simulations(data_dir, sim_source, bot_repo, sim_module, timeout)))
    return out
