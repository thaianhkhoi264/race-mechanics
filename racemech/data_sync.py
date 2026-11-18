"""
Refresh this project's local data.

1. Copy the game clients' ``master.mdb`` databases (Global, and JP if installed) into
   ``<data_dir>/game/``. Copies mean a running or patching game is never touched; this
   is the source of skills, names, track names and the released Champions Meeting list.
2. Download course geometry (corners, straights, slopes) from community skill data. The game
   keeps geometry in asset bundles, not in master.mdb, so this is the only online fetch;
   the file is cached and only changes when new racecourses are added.
"""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

from racemech.gamedata import game_dir

COURSE_DATA_URL = "<course data URL>"


def course_data_path(data_dir: Path) -> Path:
    return data_dir / "course_data.json"


def _atomic_copy(src: Path, dest: Path) -> int:
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    shutil.copyfile(src, tmp)
    tmp.replace(dest)
    return dest.stat().st_size


def sync(data_dir: Path, global_master: Path, jp_master: Path | None,
         download_courses: bool = True, timeout: float = 60.0) -> list[tuple[str, str]]:
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
    return out
