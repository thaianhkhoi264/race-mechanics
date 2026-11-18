"""
Pull the concrete things a question is about out of free text, in code (no model):
skills (typo tolerant), CM number, running styles, Stamina, recovery size, debuffer count.

Ambiguities are not resolved silently: they are recorded in ``Entities.notes`` so the
model can mention the assumption (e.g. "0.35 recovery" read as 3.5%).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

STYLE_WORDS = {
    "front": ["front runner", "front-runner", "frontrunner", "runner style", "nige", "front"],
    "pace": ["pace chaser", "pace-chaser", "pacechaser", "senkou", "leader", "pace"],
    "late": ["late surger", "late-surger", "latesurger", "sashi", "betweener", "late"],
    "end": ["end closer", "end-closer", "endcloser", "oikomi", "closer", "chaser"],
}
WHITE_RECOVERY = 0.015


@dataclass
class SkillMatch:
    sid: str
    name: str
    score: float
    matched: str


@dataclass
class Entities:
    skills: list[SkillMatch] = field(default_factory=list)
    cm: int | None = None
    styles: list[str] = field(default_factory=list)
    stamina: float | None = None
    recoveries: list[float] = field(default_factory=list)   # fractions of max HP
    debuffers: int | None = None
    notes: list[str] = field(default_factory=list)


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("◎", " ").replace("○", " ").replace("×", " ")
    text = re.sub(r"[^a-z0-9#%.\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class SkillMatcher:
    """Fuzzy skill-name matching over Global names (JP-only skills match only by ID)."""

    def __init__(self, skills: dict, min_len: int = 5):
        # skills: sid -> object with .name and .source
        self.by_name: dict[str, list[str]] = {}
        for sid, s in skills.items():
            if s.source != "global" or sid.startswith("9"):
                continue                      # inherited copies share the unique's name
            key = normalise(s.name)
            if len(key) >= min_len:
                self.by_name.setdefault(key, []).append(sid)
        self.names = list(self.by_name)
        self.skills = skills

    def _pick(self, sids: list[str]) -> str:
        # Tier families share a base name (Right-Handed ◎/○/×): prefer ◎, then ○, never ×.
        def rank(sid):
            n = self.skills[sid].name
            return 0 if "◎" in n else 1 if "○" in n else 3 if "×" in n else 2
        return sorted(sids, key=rank)[0]

    def find(self, question: str, threshold: float = 88) -> list[SkillMatch]:
        q = normalise(question)
        found: list[SkillMatch] = []
        # 1) exact names, longest first, consuming the matched span
        rest = f" {q} "
        for name in sorted(self.names, key=len, reverse=True):
            if f" {name} " in rest:
                sid = self._pick(self.by_name[name])
                found.append(SkillMatch(sid, self.skills[sid].name, 100.0, name))
                rest = rest.replace(f" {name} ", " | ")
        # 2) typo-tolerant pass on the remaining text, word windows of 1-5
        words = [w for w in rest.split() if w != "|"]
        seen = {m.sid for m in found}
        for size in range(5, 0, -1):
            for i in range(len(words) - size + 1):
                window = " ".join(words[i:i + size])
                if len(window) < 6:
                    continue
                hit = process.extractOne(window, self.names, scorer=fuzz.ratio, score_cutoff=threshold)
                if hit:
                    sid = self._pick(self.by_name[hit[0]])
                    if sid not in seen:
                        found.append(SkillMatch(sid, self.skills[sid].name, hit[1], window))
                        seen.add(sid)
        return found


def extract(question: str, matcher: SkillMatcher | None = None) -> Entities:
    e = Entities()
    q = normalise(question)

    m = re.search(r"\bcm\s*#?\s*(\d{1,3})\b", q) or re.search(r"champions? meeting\s*#?\s*(\d{1,3})", q)
    if m:
        e.cm = int(m.group(1))

    for style, words in STYLE_WORDS.items():
        if any(re.search(rf"\b{re.escape(w)}s?\b", q) for w in words):
            e.styles.append(style)
    # "pace chaser" also contains "chaser"; drop End when only the Pace phrase matched
    if "pace" in e.styles and "end" in e.styles and not re.search(r"end closer|closer|oikomi", q):
        e.styles.remove("end")

    m = (re.search(r"(\d{3,4})\s*(?:stamina|stam|sta)\b", q)
         or re.search(r"\b(?:stamina|stam)\s*(?:of|at|is|=)?\s*(\d{3,4})\b", q))
    if m:
        e.stamina = float(m.group(1))

    m = re.search(r"(\d+)\s*debuffers?\b", q) or re.search(r"\b(one|two|three|four|five)\s+debuffers?\b", q)
    if m:
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
        e.debuffers = int(words.get(m.group(1), m.group(1)) if m.group(1) in words else m.group(1))

    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(%)?\s*(?:hp\s*)?(?:recovery|heal|recover)", q):
        val, pct = float(m.group(1)), m.group(2)
        if pct:
            e.recoveries.append(val / 100)
        elif val < 0.1:
            e.recoveries.append(val)                      # already a fraction, e.g. 0.035
        elif val < 1:
            e.recoveries.append(val / 10)
            e.notes.append(f'"{m.group(1)} recovery" was read as {val * 10:g}% of max HP '
                           f"(a {val * 100:g}% recovery does not exist; skills show it as {val / 10:g}).")
        else:
            e.recoveries.append(val / 100)
            e.notes.append(f'"{m.group(1)} recovery" was read as {val:g}% of max HP.')
    if re.search(r"\bwhite\s+(?:recovery|heal)", q):
        e.recoveries.append(WHITE_RECOVERY)

    if matcher is not None:
        e.skills = matcher.find(question)
        if re.search(r"\binherit", q):
            for sm in e.skills:
                if sm.sid.startswith("1") and "9" + sm.sid[1:] in matcher.skills:
                    sm.sid = "9" + sm.sid[1:]
    return e
