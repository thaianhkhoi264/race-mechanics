"""
Read-only adapter around the bot_repo calculator modules.

The bot already has tested, deterministic code for skill trigger windows
(``skill_describe``, ``skill_chart``) and the stamina model (``stamina_module``).
Rather than copy it (and let the two drift), this module imports it from a local
checkout of the bot and feeds it this project's own data: skills from the game's
``master.mdb`` (Global first, JP only for missing skills) and cached course geometry.
Nothing in the bot repo is written to.

All access to bot internals goes through ``BotLib`` so a vendored copy could replace it
later without touching the rest of this package.
"""
from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from racemech import gamedata
from racemech.data_sync import course_data_path


class BotLibError(RuntimeError):
    """The bot checkout or the synced data is missing or unusable."""


@dataclass
class Course:
    course_id: int
    entry: dict           # community skill data course_data entry (geometry)
    display: str          # e.g. "CM#22 — Tokyo 1600m Dirt, Left, Soft, Winter, Snow"
    cm: dict | None       # {"ground", "season", "weather", ...} for a CM, else None
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
        try:
            self.game = gamedata.load(self.data_dir)
        except FileNotFoundError as exc:
            raise BotLibError(f"{exc}") from exc
        geometry = course_data_path(self.data_dir)
        if not geometry.is_file():
            raise BotLibError(f"No course geometry at {geometry}; run `racemech sync`")

        if str(self.bot_repo) not in sys.path:
            sys.path.insert(0, str(self.bot_repo))
        try:
            self.cm = importlib.import_module("cm_module")
            self.describe = importlib.import_module("skill_describe")
            self.stamina = importlib.import_module("stamina_module")
        except ImportError as exc:
            raise BotLibError(f"Could not import the bot modules ({exc}); install the [bot] extra") from exc

        self.skill_data: dict = self.game.skill_data
        self.skill_names: dict = self.game.skill_names

        cm = self.cm
        cm.load_local_data_if_needed()        # bot's own paths; finds nothing on this PC
        cm._skill_data = self.skill_data
        cm._skill_names = self.skill_names
        with geometry.open(encoding="utf-8") as f:
            cm._course_data = json.load(f)
        for tid, name in self.game.track_names.items():
            cm._track_name_to_id[name] = tid
            cm._track_id_to_name[tid] = name

        st = self.stamina
        st._skill_data, st._skill_names = self.skill_data, self.skill_names
        global_only = {s: e for s, e in self.skill_data.items() if self.game.skills[s].source == "global"}
        st._skill_averages = st._scan_recovery_debuff_averages(global_only, self.skill_names)
        st._data_loaded = True

        self._loaded = True
        return self

    # --------------------------------------------------------------- lookups

    def skill(self, sid: str) -> gamedata.Skill | None:
        return self.game.skills.get(sid)

    def skill_name(self, sid: str) -> str | None:
        s = self.game.skills.get(sid)
        return s.name if s else None

    def course_for_cm(self, number: int) -> Course | None:
        """A released Champions Meeting from the Global database (future ones are not known)."""
        c = self.game.champions.get(number)
        if c is None:
            return None
        entry = self.cm.get_course_entry(c.course_set)
        if entry is None:
            return None
        display = (f"CM#{c.number} — {c.track_name} {c.distance}m {c.surface}, {c.turn}, "
                   f"{c.ground}, {c.season}, {c.weather}")
        cm = {"number": c.number, "ground": c.ground, "season": c.season, "weather": c.weather}
        return Course(c.course_set, entry, display, cm, True)

    def current_cm_number(self, now: datetime | None = None) -> int | None:
        """The running CM, else the next one, else the latest known."""
        ts = (now or datetime.now(UTC)).timestamp()
        cms = sorted(self.game.champions.values(), key=lambda c: c.number)
        for c in cms:
            if c.start_ts <= ts <= c.end_ts or c.start_ts > ts:
                return c.number
        return cms[-1].number if cms else None
