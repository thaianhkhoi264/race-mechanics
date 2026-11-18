"""
Read-only adapter around the bot_repo calculator modules.

The bot already has tested, deterministic code for skill trigger windows
(``skill_describe``, ``skill_chart``), course / CM resolution (``cm_module``)
and the stamina model (``stamina_module``). Rather than copy it (and let the two
drift), this module imports it from a local checkout of the bot and feeds it
this project's own downloaded data. Nothing in the bot repo is written to.

All access to bot internals goes through ``BotLib`` so a vendored copy could
replace it later without touching the rest of this package.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from racemech.data_sync import uma_tools_dir


class BotLibError(RuntimeError):
    """The bot checkout or the synced data is missing or unusable."""


@dataclass
class Course:
    course_id: int
    entry: dict           # community skill data course_data entry
    display: str          # e.g. "CM#22 — Tokyo 1600m Dirt, Left, Soft, Winter, Snow"
    cm: dict | None       # parsed CM event (venue, ground, season, ...) or None for a plain course
    is_cm: bool


class BotLib:
    def __init__(self, bot_repo: Path, data_dir: Path):
        self.bot_repo = Path(bot_repo)
        self.data_dir = Path(data_dir)
        self._loaded = False

    # ------------------------------------------------------------------ setup

    def load(self) -> BotLib:
        if self._loaded:
            return self
        if not (self.bot_repo / "skill_describe.py").is_file():
            raise BotLibError(f"bot_repo checkout not found at {self.bot_repo} (set bot_repo)")
        src = uma_tools_dir(self.data_dir)
        if not (src / "skill_data.json").is_file():
            raise BotLibError(f"No game data in {src}; run `racemech sync` first")

        if str(self.bot_repo) not in sys.path:
            sys.path.insert(0, str(self.bot_repo))
        try:
            self.cm = importlib.import_module("cm_module")
            self.describe = importlib.import_module("skill_describe")
            self.stamina = importlib.import_module("stamina_module")
            self.chart = importlib.import_module("skill_chart")
        except ImportError as exc:
            raise BotLibError(f"Could not import the bot modules ({exc}); install the [bot] extra") from exc

        def read(name):
            with (src / name).open(encoding="utf-8") as f:
                return json.load(f)

        self.skill_data: dict = read("skill_data.json")
        self.skill_names: dict = read("skillnames.json")

        cm = self.cm
        cm.load_local_data_if_needed()        # bot's own paths; no-op data on this PC
        cm._skill_data = self.skill_data
        cm._skill_names = self.skill_names
        cm._course_data = read("course_data.json")
        cm._course_labels = read("course_labels.json")
        for tid, names in read("tracknames.json").items():
            en = names[1] if isinstance(names, list) and len(names) > 1 else str(names)
            cm._track_name_to_id[en] = int(tid)
            cm._track_id_to_name[int(tid)] = en

        st = self.stamina
        st._skill_data, st._skill_names = self.skill_data, self.skill_names
        st._skill_averages = st._scan_recovery_debuff_averages(self.skill_data, self.skill_names)
        st._data_loaded = True

        self._loaded = True
        return self

    # --------------------------------------------------------------- lookups

    def skill_name(self, sid: str) -> str | None:
        raw = self.skill_names.get(sid)
        if not raw:
            return None
        name = raw[0] if isinstance(raw, list) else str(raw)
        return name or None

    def cm_events(self) -> list[dict]:
        """CM events from the live events timeline (cached by the bot module for 1 h)."""
        return asyncio.run(self.cm.fetch_cm_events())

    def course_for_cm(self, number: int) -> Course | None:
        events = self.cm_events()
        cm = next((c for c in events if c["number"] == number), None)
        course_id, display = self.cm.resolve_course(f"cm:{number}", None)
        if not cm or not course_id:
            return None
        return Course(course_id, self.cm.get_course_entry(course_id), display, cm, True)

    def current_cm_number(self) -> int | None:
        self.cm_events()
        cm = self.cm.get_active_cm() or self.cm.get_next_cm()
        return cm["number"] if cm else None
