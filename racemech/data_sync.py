"""
Download the public game data this project needs into ``<data_dir>/uma_tools``.

Same sources as the bot_repo codebase's ``skill_sync.py`` (community skill data / uma-tools on
GitHub), fetched independently so nothing depends on the remote host. Files are written
atomically (``.tmp`` then rename) so a failed download never leaves half a file.
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

_UST = "<skill data URL>"
_UT = "<skill data URL>"

# local file name -> URL. The bot's names are kept so its loaders work unchanged.
FILES: dict[str, str] = {
    "skill_data.json": f"{_UST}/skill_data.json",
    "course_data.json": f"{_UST}/course_data.json",
    "tracknames.json": f"{_UST}/tracknames.json",
    "skillnames.json": f"{_UT}/skillnames.json",
    "course_labels.json": f"{_UT}/course_data.json",
}


def uma_tools_dir(data_dir: Path) -> Path:
    return data_dir / "uma_tools"


def oldest_age_hours(data_dir: Path) -> float | None:
    """Age of the oldest file in hours, or None if any file is missing."""
    paths = [uma_tools_dir(data_dir) / name for name in FILES]
    if not all(p.is_file() for p in paths):
        return None
    return (time.time() - min(p.stat().st_mtime for p in paths)) / 3600


def sync(data_dir: Path, timeout: float = 60.0) -> list[tuple[str, int]]:
    """Download every file; returns (name, bytes) pairs."""
    dest_dir = uma_tools_dir(data_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, url in FILES.items():
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
        tmp = dest_dir / (name + ".tmp")
        tmp.write_bytes(body)
        tmp.replace(dest_dir / name)
        written.append((name, len(body)))
    return written
