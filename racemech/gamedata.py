"""
Game data read from the game clients' own databases (``master.mdb``, unencrypted SQLite).

Source-of-truth rule: **Global first.** A skill is taken from the Global client; the JP
client is consulted only for skill IDs Global does not have, and those are marked
``source="jp"`` so they are never presented as Global facts. Skill IDs are identical across
versions; JP names are Japanese.

``racemech sync`` copies the databases into ``<data_dir>/game/`` (so a running or
patching game is never touched) and this module only ever opens those copies read-only.

Skills are converted to the community skill data JSON shape the bot_repo calculators
already consume:

    {"rarity": int, "wisdomCheck": int, "tags": [int],
     "alternatives": [{"condition", "precondition", "baseDuration", "durationScaling",
                       "cooldown", "effects": [{"type", "modifier", "target", "scaling"}]}]}
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

# text_data categories
_SKILL_NAME = 47
_SKILL_DESC = 48
_TRACK_NAME = 35

GROUND_CONDITION = {1: "Firm", 2: "Good", 3: "Soft", 4: "Heavy"}
SEASON = {1: "Spring", 2: "Summer", 3: "Fall", 4: "Winter", 5: "Spring"}
WEATHER = {1: "Sunny", 2: "Cloudy", 3: "Rainy", 4: "Snow"}
SURFACE = {1: "Turf", 2: "Dirt"}
TURN = {1: "Right", 2: "Left", 4: "Straight"}


def game_dir(data_dir: Path) -> Path:
    return data_dir / "game"


@dataclass
class Skill:
    sid: str
    name: str
    description: str
    source: str          # "global" or "jp"
    entry: dict          # community skill data shaped


@dataclass
class ChampionsMeeting:
    number: int
    start_ts: int
    end_ts: int
    course_set: int      # same id as community skill data course_data keys
    track_id: int
    track_name: str
    distance: int
    surface: str
    turn: str
    ground: str
    season: str
    weather: str


GRADE = {1: "G", 2: "F", 3: "E", 4: "D", 5: "C", 6: "B", 7: "A", 8: "S"}
STYLE_IDS = {1: "front", 2: "pace", 3: "late", 4: "end"}


@dataclass
class Card:
    """One playable character version (a "card"), from the Global client."""
    card_id: int
    chara_id: int
    name: str                      # "Satono Diamond"
    title: str                     # "[Jade's Prosperity]"
    default_style: str | None      # the game's default running style: front/pace/late/end
    distance: dict[str, str]       # sprint/mile/medium/long -> grade letter
    style: dict[str, str]          # front/pace/late/end -> grade letter
    ground: dict[str, str]         # turf/dirt -> grade letter
    unique: str | None             # unique skill id
    built_in: list[tuple[str, int]] = field(default_factory=list)   # (skill id, potential level 0-5)


@dataclass
class GameData:
    skills: dict[str, Skill] = field(default_factory=dict)
    track_names: dict[int, str] = field(default_factory=dict)
    champions: dict[int, ChampionsMeeting] = field(default_factory=dict)
    cards: dict[int, Card] = field(default_factory=dict)

    @property
    def skill_data(self) -> dict:
        """sid -> community skill data entry (what the bot calculators expect)."""
        return {sid: s.entry for sid, s in self.skills.items()}

    @property
    def skill_names(self) -> dict:
        """sid -> [name], the uma-tools skillnames.json shape."""
        return {sid: [s.name] for sid, s in self.skills.items()}


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _texts(con: sqlite3.Connection, category: int) -> dict[int, str]:
    return {r["index"]: r["text"] for r in con.execute(
        "select [index], text from text_data where category = ?", (category,))}


def row_to_entry(r: sqlite3.Row) -> dict:
    """One skill_data row -> community skill data entry."""
    alternatives = []
    for alt in (1, 2):
        cond = r[f"condition_{alt}"] or ""
        if not cond:
            continue
        effects = []
        for n in (1, 2, 3):
            etype = r[f"ability_type_{alt}_{n}"]
            if not etype:
                continue
            effects.append({
                "type": etype,
                "modifier": r[f"float_ability_value_{alt}_{n}"],
                "target": r[f"target_type_{alt}_{n}"],
                "scaling": r[f"ability_value_usage_{alt}_{n}"],
            })
        alternatives.append({
            "condition": cond,
            "precondition": r[f"precondition_{alt}"] or "",
            "baseDuration": r[f"float_ability_time_{alt}"],
            "durationScaling": r[f"ability_time_usage_{alt}"],
            "cooldown": r[f"float_cooldown_time_{alt}"],
            "effects": effects,
        })
    tags = [int(t) for t in str(r["tag_id"] or "").split("/") if t.strip().isdigit()]
    return {"rarity": r["rarity"], "wisdomCheck": r["activate_lot"], "tags": tags,
            "alternatives": alternatives}


def _read_skills(con: sqlite3.Connection, source: str) -> dict[str, Skill]:
    names, descs = _texts(con, _SKILL_NAME), _texts(con, _SKILL_DESC)
    out = {}
    for r in con.execute("select * from skill_data"):
        sid = r["id"]
        name = names.get(sid)
        if not name:
            continue                      # unnamed internal/event rows
        out[str(sid)] = Skill(str(sid), name, (descs.get(sid) or "").replace("\\n", " "),
                              source, row_to_entry(r))
    return out


def _read_champions(con: sqlite3.Connection, track_names: dict[int, str]) -> dict[int, ChampionsMeeting]:
    q = """
        select s.id, s.start_date, s.end_date, cs.id as course_set, cs.race_track_id, cs.distance,
               cs.ground as surface, cs.turn, cond.season, cond.weather, cond.ground as ground_condition
        from champions_schedule s
        join champions_race_condition rc on rc.champions_id = s.id
        join race_instance ri on ri.id = rc.race_instance_id
        join race r on r.id = ri.race_id
        join race_course_set cs on cs.id = r.course_set
        join race_condition cond on cond.id = rc.race_condition_id
        order by s.id, rc.round_id
    """
    out: dict[int, ChampionsMeeting] = {}
    for r in con.execute(q):
        if r["id"] in out:                # every round of a CM uses the same course/conditions
            continue
        out[r["id"]] = ChampionsMeeting(
            number=r["id"], start_ts=r["start_date"], end_ts=r["end_date"],
            course_set=r["course_set"], track_id=r["race_track_id"],
            track_name=track_names.get(r["race_track_id"], str(r["race_track_id"])),
            distance=r["distance"], surface=SURFACE.get(r["surface"], "?"), turn=TURN.get(r["turn"], "?"),
            ground=GROUND_CONDITION.get(r["ground_condition"], "?"), season=SEASON.get(r["season"], "?"),
            weather=WEATHER.get(r["weather"], "?"))
    return out


_CARD_TITLE = 5
_CHARA_NAME = 6


def _read_cards(con: sqlite3.Connection) -> dict[int, Card]:
    """Playable cards: aptitudes and unique skill from the highest rarity row, built-in skills
    (available_skill_set: need_rank 0 at the start, 2-5 unlocked by potential level)."""
    tables = {r[0] for r in con.execute("select name from sqlite_master where type = 'table'")}
    if not {"card_data", "card_rarity_data", "skill_set", "available_skill_set"} <= tables:
        return {}
    titles, chara_names = _texts(con, _CARD_TITLE), _texts(con, _CHARA_NAME)
    rarity_rows = {}
    for r in con.execute("select * from card_rarity_data order by card_id, rarity"):
        rarity_rows[r["card_id"]] = r                  # last = highest rarity
    built: dict[int, list[tuple[str, int]]] = {}
    for r in con.execute("select available_skill_set_id, skill_id, need_rank from available_skill_set "
                         "order by need_rank, skill_id"):
        built.setdefault(r["available_skill_set_id"], []).append((str(r["skill_id"]), r["need_rank"]))
    out = {}
    for c in con.execute("select * from card_data"):
        rr = rarity_rows.get(c["id"])
        name = chara_names.get(c["chara_id"])
        if rr is None or not name:
            continue
        unique = con.execute("select skill_id1 from skill_set where id = ?", (rr["skill_set"],)).fetchone()
        out[c["id"]] = Card(
            card_id=c["id"], chara_id=c["chara_id"], name=name, title=titles.get(c["id"], ""),
            default_style=STYLE_IDS.get(c["running_style"]),
            distance={k: GRADE.get(rr[f"proper_distance_{col}"], "?") for k, col in
                      (("sprint", "short"), ("mile", "mile"), ("medium", "middle"), ("long", "long"))},
            style={k: GRADE.get(rr[f"proper_running_style_{col}"], "?") for k, col in
                   (("front", "nige"), ("pace", "senko"), ("late", "sashi"), ("end", "oikomi"))},
            ground={k: GRADE.get(rr[f"proper_ground_{k}"], "?") for k in ("turf", "dirt")},
            unique=str(unique[0]) if unique and unique[0] else None,
            built_in=built.get(c["available_skill_set_id"], []))
    return out


def load(data_dir: Path) -> GameData:
    """Global database first; JP only fills skill IDs Global lacks."""
    gd = game_dir(data_dir)
    global_db, jp_db = gd / "global_master.mdb", gd / "jp_master.mdb"
    if not global_db.is_file():
        raise FileNotFoundError(f"{global_db} missing; run `racemech sync` with the Global game installed")
    data = GameData()
    with closing(_connect(global_db)) as con:
        data.skills = _read_skills(con, "global")
        data.track_names = _texts(con, _TRACK_NAME)
        data.champions = _read_champions(con, data.track_names)
        data.cards = _read_cards(con)
    if jp_db.is_file():
        with closing(_connect(jp_db)) as con:
            for sid, skill in _read_skills(con, "jp").items():
                data.skills.setdefault(sid, skill)
    return data
