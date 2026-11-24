"""
Characters (cards): which version a question means, how she should be run, and which of her
own skills restore HP on a course.

Facts come from the Global ``master.mdb`` (aptitudes, unique skill, built-in skills). The community
character database's ``character-cards.json`` only supplies version tags ("new_year") so community names like
"NY Dia" resolve to a card; nicknames and version words live in ``knowledge/aliases.yaml``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from racemech.entities import ALIASES_FILE, normalise
from racemech.gamedata import Card, Skill

STYLE_NAME = {"front": "Front Runner", "pace": "Pace Chaser", "late": "Late Surger", "end": "End Closer"}
STYLE_IDS = {"1": "front", "2": "pace", "3": "late", "4": "end"}
DISTANCE_TYPES = {1: "sprint", 2: "mile", 3: "medium", 4: "long"}
DISTANCE_RANGES = {"sprint": "Sprint (under 1600 m)", "mile": "Mile (1600-1999 m)",
                   "medium": "Medium (2000-2499 m)", "long": "Long (2500 m or more)"}
GRADE_ORDER = "GFEDCBAS"

# Version tags whose display name is not plain title case (from the character database's own table).
VERSION_NAMES = {
    "alt": "Alt Version", "fall_festival": "Festival", "grand_live": "Grand Concert", "blaze": "BLAZE",
    "sports_fest": "Sports Festival", "larc": "Project L'Arc", "uaf": "U.A.F.",
    "gff": "Great Food Festival", "twinkle": "The Twinkle Legends", "island": "Deserted Island",
    "tracen_ken": "Tracen-ken", "five_point_five_anni": "5.5th Anni",
}

# Typical placings in a 9-runner Champions Meeting by running style (an assumption, used only to
# say whether a position-gated recovery is likely to fire).
TYPICAL_PLACINGS = {"front": (1, 2), "pace": (2, 4), "late": (4, 7), "end": (6, 9)}
FIELD = 9

# Condition fields that only describe where on the course / which race; anything else
# (placing, nearby runners, rushed, HP ...) makes activation depend on how the race goes.
_GEOGRAPHY = {"distance_type", "running_style", "phase", "phase_random", "phase_firsthalf_random",
              "phase_laterhalf_random", "phase_corner_random", "phase_straight_random",
              "phase_firstquarter_random", "distance_rate", "remain_distance", "is_finalcorner",
              "is_finalcorner_random", "corner", "corner_random", "all_corner_random", "straight_random",
              "is_lastspurt", "is_last_straight", "is_last_straight_onetime", "track_id", "ground_type",
              "ground_condition", "season", "weather", "rotation", "is_basis_distance", "slope",
              "up_slope_random", "down_slope_random", "straight_front_type", "lane_type"}
_TOKEN = re.compile(r"([a-z_0-9]+)(>=|<=|==|!=|>|<)(-?\d+)")


def version_name(tag: str | None) -> str:
    if not tag:
        return "Original"
    return VERSION_NAMES.get(tag, tag.replace("_", " ").title())


def load_versions(path: Path) -> dict[int, str | None]:
    """card_id -> version tag (None for the original version)."""
    if not path.is_file():
        return {}
    try:
        cards = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {int(c["card_id"]): c.get("version") for c in cards if "card_id" in c}


@dataclass
class CharacterMatch:
    card: Card
    version: str                       # display name, "Original" for the base version
    notes: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        return f"{self.card.name} ({self.version})"


class CharacterMatcher:
    def __init__(self, cards: dict[int, Card], versions: dict[int, str | None],
                 aliases_file: Path = ALIASES_FILE):
        self.cards, self.versions = cards, versions
        data = yaml.safe_load(aliases_file.read_text(encoding="utf-8")) if aliases_file.is_file() else {}
        self.by_name: dict[str, list[int]] = {}
        for cid, c in cards.items():
            self.by_name.setdefault(normalise(c.name), []).append(cid)
        self.nicknames = {normalise(k): normalise(v) for k, v in (data.get("characters") or {}).items()
                          if normalise(v) in self.by_name}
        self.titles = {normalise(c.title.strip("[]")): cid for cid, c in cards.items() if c.title}
        words: dict[str, str] = {}
        for tag in {t for t in versions.values() if t}:
            words[normalise(version_name(tag))] = tag
            words[normalise(tag.replace("_", " "))] = tag
        for k, v in (data.get("versions") or {}).items():
            words[normalise(k)] = v or "original"
        self.version_words = words

    def _tag(self, cid: int) -> str | None:
        return self.versions.get(cid)

    def find(self, question: str) -> CharacterMatch | None:
        q = f" {normalise(question)} "
        for title, cid in sorted(self.titles.items(), key=lambda kv: -len(kv[0])):
            if len(title) >= 6 and f" {title} " in q:
                c = self.cards[cid]
                return CharacterMatch(c, version_name(self._tag(cid)),
                                      [f'"{c.title}" is {c.name} ({version_name(self._tag(cid))}).'])
        names = list(self.by_name) + list(self.nicknames)
        hit = next((n for n in sorted(names, key=len, reverse=True) if f" {n} " in q), None)
        if hit is None:
            return None
        name = self.nicknames.get(hit, hit)
        cids = sorted(self.by_name[name])
        notes = [] if hit == name else [f'"{hit}" read as the character {self.cards[cids[0]].name}.']
        wanted = next((tag for w, tag in sorted(self.version_words.items(), key=lambda kv: -len(kv[0]))
                       if f" {w} " in q), None)
        by_tag = {(self._tag(c) or "original"): c for c in cids}
        if wanted and wanted in by_tag:
            cid = by_tag[wanted]
        else:
            cid = by_tag.get("original", cids[0])
            others = [version_name(self._tag(c)) for c in cids if c != cid]
            if wanted:
                notes.append(f"{self.cards[cid].name} has no {version_name(wanted)} version on Global; "
                             f"using {version_name(self._tag(cid))}.")
            elif others:
                chosen = f"{self.cards[cid].name} ({version_name(self._tag(cid))})"
                notes.append(f"No version was named, so {chosen} was assumed; other Global versions: "
                             f"{', '.join(others)}.")
        return CharacterMatch(self.cards[cid], version_name(self._tag(cid)), notes)


# ------------------------------------------------------------------ analysis

def _conditions(entry: dict) -> list[str]:
    return [f"{a.get('condition', '')}&{a.get('precondition', '')}" for a in entry.get("alternatives", [])]


def skill_styles(entry: dict) -> set[str]:
    """Running styles a skill is locked to (empty = any style)."""
    out = set()
    for cond in _conditions(entry):
        out |= {STYLE_IDS[v] for f, op, v in _TOKEN.findall(cond) if f == "running_style" and op == "=="
                and v in STYLE_IDS}
    return out


def skill_distances(entry: dict) -> set[str]:
    out = set()
    for cond in _conditions(entry):
        out |= {DISTANCE_TYPES[int(v)] for f, op, v in _TOKEN.findall(cond)
                if f == "distance_type" and op == "==" and int(v) in DISTANCE_TYPES}
    return out


def _grade(card: Card, style: str) -> int:
    return GRADE_ORDER.index(card.style.get(style, "G"))


def style_verdict(card: Card, skills: dict[str, Skill]) -> dict:
    """Which style to run: styles with the best aptitude (A or S if any), then her own skills' votes."""
    best = max(_grade(card, s) for s in STYLE_NAME)
    floor = min(best, GRADE_ORDER.index("A"))
    candidates = [s for s in STYLE_NAME if _grade(card, s) >= floor]
    votes = dict.fromkeys(STYLE_NAME, 0)
    for sid in [card.unique] + [s for s, _ in card.built_in]:
        if sid and sid in skills:
            for st in skill_styles(skills[sid].entry):
                votes[st] += 1
    ranked = sorted(candidates, key=lambda s: -votes[s])
    dominant = None
    if len(candidates) == 1:
        dominant = candidates[0]
    elif votes[ranked[0]] >= 2 and votes[ranked[0]] >= 3 * votes[ranked[1]]:     # a clear majority
        dominant = ranked[0]
    return {"dominant": dominant, "candidates": candidates, "votes": votes}


def _ord(n: int) -> str:
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n if n < 20 else n % 10, 'th') }"


def _placing_range(cond: str) -> tuple[int, int] | None:
    """Placings (1-9) a condition allows, from order / order_rate (rounded to nearest)."""
    lo, hi, seen = 1, FIELD, False
    for f, op, v in _TOKEN.findall(cond):
        if f not in ("order", "order_rate"):
            continue
        seen = True
        n = int(v) if f == "order" else round(int(v) * FIELD / 100)
        if op in (">=", "=="):
            lo = max(lo, n)
        if op == ">":
            lo = max(lo, n + 1)
        if op in ("<=", "=="):
            hi = min(hi, n)
        if op == "<":
            hi = min(hi, n - 1)
    return (lo, hi) if seen else None


@dataclass
class Recovery:
    sid: str
    name: str
    pct: float                 # fraction of max HP restored to herself
    kind: str                  # "unique" | "gold built-in" | "white built-in"
    status: str                # "fires" | "likely" | "possible" | "unlikely" | "no"
    reason: str


def course_recoveries(card: Card, skills: dict[str, Skill], distance_type: int, style: str,
                      activates: dict[str, str]) -> list[Recovery]:
    """Her unique and built-in skills that restore her own HP, judged for one course and style."""
    sids = [(card.unique, "unique")] + [(s, "built-in") for s, _ in card.built_in]
    have = {s for s, _ in sids}
    out = []
    for sid, kind in sids:
        sk = skills.get(sid or "")
        if sk is None:
            continue
        effects = [e for a in sk.entry.get("alternatives", []) for e in a.get("effects", [])]
        heal = max((e["modifier"] for e in effects if e["type"] == 9 and e["target"] in (1, 2)
                    and e["modifier"] > 0), default=0)
        if not heal:
            continue
        if kind == "built-in":
            gold = sid[:-1] + "1"
            if sk.entry.get("rarity") == 1 and gold != sid and gold in have:
                continue                                 # the gold version replaces this white one
            kind = "gold built-in" if sk.entry.get("rarity") == 2 else "white built-in"
        dists, styles = skill_distances(sk.entry), skill_styles(sk.entry)
        cond = (sk.entry.get("alternatives") or [{}])[0].get("condition", "")
        if dists and DISTANCE_TYPES.get(distance_type) not in dists:
            status, reason = "no", "only on " + "/".join(DISTANCE_RANGES[d] for d in sorted(dists)) + " races"
        elif styles and style not in styles:
            status, reason = "no", f"only for {'/'.join(STYLE_NAME[s] for s in sorted(styles))}"
        else:
            rng = _placing_range(cond)
            other = {f for f, _, _ in _TOKEN.findall(cond)} - _GEOGRAPHY - {"order", "order_rate"}
            if rng:
                t_lo, t_hi = TYPICAL_PLACINGS[style]
                where = (f"needs {_ord(rng[0])}-{_ord(rng[1])} place" if rng[0] != rng[1]
                         else f"needs {_ord(rng[0])} place")
                if rng[0] <= t_lo and t_hi <= rng[1]:
                    status = "likely"
                elif rng[1] < t_lo or rng[0] > t_hi:
                    status = "unlikely"
                else:
                    status = "possible"
                reason = f"{where}; a {STYLE_NAME[style]} is usually {_ord(t_lo)}-{_ord(t_hi)}"
            elif other:
                status, reason = "possible", "depends on how the race goes (" + ", ".join(sorted(other)) + ")"
            else:
                status, reason = "fires", "no positional condition"
            if sid in activates:
                reason += f"; {activates[sid]}"
        out.append(Recovery(sid, sk.name, heal / 10000, kind, status, reason))
    return out
