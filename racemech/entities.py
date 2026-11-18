"""
Pull the concrete things a question is about out of free text, in code (no model).

Built for how players actually type: shorthand (OYL, PTTM, GW), partial names ("standard
distance", "tokyo"), typos, counts ("2 subdued"), and intent ("has X" vs "should I buy X").
Every guess the matcher makes is recorded in ``Entities.notes`` so the model states it.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rapidfuzz import fuzz, process

ALIASES_FILE = Path(__file__).parent / "knowledge" / "aliases.yaml"

STYLE_WORDS = {
    "front": ["front runner", "front-runner", "frontrunner", "nige", "runner style", "front"],
    "pace": ["pace chaser", "pace-chaser", "pacechaser", "senkou", "leader", "pace"],
    "late": ["late surger", "late-surger", "latesurger", "sashi", "betweener", "late"],
    "end": ["end closer", "end-closer", "endcloser", "oikomi", "closer"],
}
STYLE_PLURAL = {"front": "Front Runners", "pace": "Pace Chasers",
                "late": "Late Surgers", "end": "End Closers"}
WHITE_RECOVERY = 0.015
GOLD_RECOVERY = 0.055

# Clauses that ask about acquiring something rather than state that the runner has it.
_BUY = re.compile(r"\b(should i|shall i|do i need|worth (?:buying|getting|it|taking)|would .{0,20}help|"
                  r"is .{0,40} worth|buy|purchase|pick up|get (?:a|an|the)?\s?(?:white|gold)?)\b")
_OWN = re.compile(r"\b(has|have|having|got|with|owns?|learned|equipped|already)\b")
_VENUE_PREP = re.compile(r"\b(?:in|at|on|for|course|cm)\s*$")
# Short common words that must never be read as an acronym alias.
_NOT_ACRONYMS = set("""a an and are as at be but by can cm do for get got had has have he her his how i if in
is it its me my no not of on or our she so the to too up us was we who why you see set run sat sta stam
spd pow wit hp bad best yes""".split())


@dataclass
class SkillMatch:
    sid: str
    name: str
    score: float
    matched: str
    count: int = 1
    role: str = "owned"          # owned | candidate (asking whether to buy) | opponent (a debuff on you)
    note: str | None = None


@dataclass
class Entities:
    skills: list[SkillMatch] = field(default_factory=list)
    cm: int | None = None
    styles: list[str] = field(default_factory=list)
    stamina: float | None = None
    wit: float | None = None
    power: float | None = None
    recoveries: list[float] = field(default_factory=list)            # owned, fractions of max HP
    candidate_recoveries: list[float] = field(default_factory=list)  # "should I buy a white recovery"
    debuffers: int | None = None
    asks_how_many: bool = False
    notes: list[str] = field(default_factory=list)


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[◎○×☆★♪!?,:;()\"“”'’/]", " ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)          # keep decimal points only
    text = text.replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def _base(name: str) -> str:
    return re.sub(r"\s*[◎○×]\s*$", "", name).strip()


def _acronym(base: str) -> str | None:
    words = normalise(base).split()
    if len(words) < 3:
        return None
    acro = "".join(w[0] for w in words if w[0].isalpha())
    return acro if len(acro) >= 3 and acro not in _NOT_ACRONYMS else None


class SkillMatcher:
    """Matches Global skills (JP-only skills match only by ID; inherited copies share names)."""

    def __init__(self, skills: dict, aliases_file: Path = ALIASES_FILE):
        self.skills = skills
        self.families: dict[str, list[str]] = {}      # base name -> sids (tier variants)
        for sid, s in skills.items():
            if s.source == "global" and not sid.startswith("9"):
                self.families.setdefault(_base(s.name), []).append(sid)
        self.phrases: dict[str, str] = {normalise(b): b for b in self.families if len(normalise(b)) >= 4}

        data = yaml.safe_load(aliases_file.read_text(encoding="utf-8")) if aliases_file.is_file() else {}
        for alias, target in (data.get("skills") or {}).items():
            if _base(target) in self.families:
                self.phrases[normalise(alias)] = _base(target)
        self.style_families = {normalise(k): v for k, v in (data.get("families") or {}).items()}

        acronyms: dict[str, list[str]] = {}
        for b in self.families:
            a = _acronym(b)
            if a:
                acronyms.setdefault(a, []).append(b)
        for a, bases in acronyms.items():
            if len(bases) == 1 and a not in self.phrases:
                self.phrases[a] = bases[0]

        self.venues = {normalise(b.removesuffix(" Racecourse")): b for b in self.families
                       if b.endswith(" Racecourse")}
        self.fuzzy_names = [n for n in self.phrases if len(n) >= 8 and " " in n]

    def _variant(self, base: str, raw: str) -> tuple[str, str | None]:
        """Pick a tier variant: as written (◎/×), else ○, else the only one."""
        sids = self.families[base]
        tiers = {self.skills[s].name[-1]: s for s in sids if self.skills[s].name[-1] in "◎○×"}
        if not tiers:
            return sorted(sids)[0], None
        for glyph, words in (("◎", ("◎", "double circle")), ("×", ("×",))):
            if glyph in tiers and any(w in raw for w in words):
                return tiers[glyph], None
        if "○" in tiers:
            return tiers["○"], f"assumed {self.skills[tiers['○']].name} (the usual tier) for \"{base}\""
        return next(iter(tiers.values())), None

    def find(self, question: str, styles: list[str], threshold: float = 90) -> list[SkillMatch]:
        q = normalise(question)
        words = q.split()
        taken = [False] * len(words)
        found: list[SkillMatch] = []

        def claim(i, j, base, score, how):
            for k in range(i, j):
                taken[k] = True
            sid, note = self._variant(base, question)
            found.append(SkillMatch(sid, self.skills[sid].name, score, " ".join(words[i:j]), note=note))

        # 1) exact names, aliases, acronyms and style families; longest spans first
        for size in range(min(8, len(words)), 0, -1):
            for i in range(len(words) - size + 1):
                if any(taken[i:i + size]):
                    continue
                span = " ".join(words[i:i + size])
                if span in self.phrases:
                    base = self.phrases[span]
                    claim(i, i + size, base, 100.0, "exact")
                    if normalise(base) != span and found[-1].note is None:
                        found[-1].note = (f'"{span}" is community shorthand for the skill {base} '
                                          "(a skill, not a character)")
                elif span in self.style_families and styles:
                    name = self.style_families[span].format(styles=STYLE_PLURAL[styles[0]])
                    if name in self.families:
                        claim(i, i + size, name, 99.0, "family")
                        found[-1].note = f'"{span}" read as {name} (matches the runner\'s style)'

        # 2) venue shorthand ("has tokyo") -> that racecourse's green skill, only when owned/bought
        for i, w in enumerate(words):
            if taken[i] or w not in self.venues:
                continue
            before = " ".join(words[max(0, i - 6):i])
            if _VENUE_PREP.search(before):
                continue
            if _OWN.search(before) or _BUY.search(before) or (i and words[i - 1] in ("and", "plus")):
                claim(i, i + 1, self.venues[w], 95.0, "venue")
                found[-1].note = (f'"{w}" read as the skill {self.skills[found[-1].sid].name}'
                                  if found[-1].note is None else found[-1].note)

        # 3) typos: fuzzy match multi-word names on untaken windows only
        seen = {m.sid for m in found}
        for size in range(5, 1, -1):
            for i in range(len(words) - size + 1):
                if any(taken[i:i + size]):
                    continue
                window = " ".join(words[i:i + size])
                hit = process.extractOne(window, self.fuzzy_names, scorer=fuzz.ratio, score_cutoff=threshold)
                if hit:
                    base = self.phrases[hit[0]]
                    sid, note = self._variant(base, question)
                    if sid not in seen:
                        for k in range(i, i + size):
                            taken[k] = True
                        m = SkillMatch(sid, self.skills[sid].name, hit[1], window, note=note)
                        m.note = f'"{window}" read as the skill {base}' + (f"; {note}" if note else "")
                        found.append(m)
                        seen.add(sid)

        for m in found:
            m.count = _count_before(q, m.matched)
        return found


_NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "both": 2}


def _count_before(q: str, phrase: str) -> int:
    m = re.search(rf"\b(\d+|one|two|three|four|five|both)\s*x?\s+{re.escape(phrase)}", q)
    if not m:
        return 1
    v = m.group(1)
    return int(v) if v.isdigit() else _NUMBER_WORDS[v]


def _sentence_of(q: str, phrase: str) -> str:
    pos = q.find(phrase)
    if pos < 0:
        return q
    start = max(q.rfind(s, 0, pos) for s in (".", "?", "!", "\n")) + 1
    return q[start:pos]


_STAT_VALUE_WORDS = {"wit": r"wit|wis|wisdom|int", "power": r"power|pow|pwr"}


def _stat_values(e: Entities, q: str) -> None:
    """Wit/Power values. "900 wit" and "wit 900" both work; in a list like "wit 1100 pow 1000"
    the order of the first stat mention decides, so 1100 is not read as Power."""
    num_first = {a: re.search(rf"(\d{{3,4}})\s*(?:{w})\b", q) for a, w in _STAT_VALUE_WORDS.items()}
    word_first = {a: re.search(rf"\b(?:{w})\s*(?:of|at|is|=|:)?\s*(\d{{3,4}})\b", q)
                  for a, w in _STAT_VALUE_WORDS.items()}
    starts = [(m.start(), "num") for m in num_first.values() if m]
    starts += [(m.start(), "word") for m in word_first.values() if m]
    if not starts:
        return
    first, second = (word_first, num_first) if min(starts)[1] == "word" else (num_first, word_first)
    for attr in _STAT_VALUE_WORDS:
        m = first[attr] or second[attr]
        if m:
            setattr(e, attr, float(m.group(1)))


def _load_terms(path: Path = ALIASES_FILE) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {k.lower(): v for k, v in (data.get("terms") or {}).items()}


JP_TERMS = _load_terms()


def extract(question: str, matcher: SkillMatcher | None = None) -> Entities:
    e = Entities()
    raw = unicodedata.normalize("NFKC", question).lower()
    q = normalise(question)

    for jp, glob in JP_TERMS.items():
        if re.search(rf"\b{re.escape(jp)}\b", q):
            e.notes.append(f'The question uses the JP term "{jp}"; the Global term is "{glob}". '
                           f'Answer with "{glob}" and mention "{jp}" once in brackets, '
                           f'e.g. "{glob} ({jp} in JP)".')

    m = re.search(r"\bcm\s*#?\s*(\d{1,3})\b", q) or re.search(r"champions? meeting\s*#?\s*(\d{1,3})", q)
    if m:
        e.cm = int(m.group(1))

    for style, words in STYLE_WORDS.items():
        if any(re.search(rf"\b{re.escape(w)}s?\b", q) for w in words):
            e.styles.append(style)
    if "pace" in e.styles and "end" in e.styles and not re.search(r"end closer|closer|oikomi", q):
        e.styles.remove("end")

    m = (re.search(r"(\d{3,4})\s*(?:stamina|stam|sta)\b", q)
         or re.search(r"\b(?:stamina|stam)\s*(?:of|at|is|=|:)?\s*(\d{3,4})\b", q))
    if m:
        e.stamina = float(m.group(1))

    _stat_values(e, q)

    m = re.search(r"(\d+|one|two|three|four|five)\s*debuffers?\b", q)
    if m:
        e.debuffers = int(m.group(1)) if m.group(1).isdigit() else _NUMBER_WORDS[m.group(1)]
    e.asks_how_many = bool(re.search(r"how many\b.{0,30}\bdebuff", q))

    def add_recovery(val: float, phrase: str):
        target = e.candidate_recoveries if _BUY.search(_sentence_of(raw, phrase)) else e.recoveries
        target.append(val)

    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(%)?\s*(?:hp\s*)?(?:recovery|heal|recover)", q):
        val, pct = float(m.group(1)), m.group(2)
        if pct:
            add_recovery(val / 100, m.group(0))
        elif val < 0.1:
            add_recovery(val, m.group(0))
        elif val < 1:
            add_recovery(val / 10, m.group(0))
            e.notes.append(f'"{m.group(1)} recovery" was read as {val * 10:g}% of max HP '
                           f"(a {val * 100:g}% recovery does not exist; skills show it as {val / 10:g}).")
        else:
            add_recovery(val / 100, m.group(0))
            e.notes.append(f'"{m.group(1)} recovery" was read as {val:g}% of max HP.')
    for m in re.finditer(r"\b(white|gold)\s+(?:recovery|heal)", raw):
        add_recovery(WHITE_RECOVERY if m.group(1) == "white" else GOLD_RECOVERY, m.group(0))
        if m.group(1) == "gold":
            e.notes.append("A gold recovery was taken as 5.5% of max HP (the common gold recoveries).")

    if matcher is not None:
        e.skills = matcher.find(question, e.styles)
        for sm in e.skills:
            if re.search(r"\binherit", q) and sm.sid.startswith("1") and "9" + sm.sid[1:] in matcher.skills:
                sm.sid = "9" + sm.sid[1:]
            sentence = _sentence_of(raw, sm.matched.split()[0])
            if _BUY.search(sentence) and not _OWN.search(sentence):
                sm.role = "candidate"
            if sm.note:
                e.notes.append(sm.note)
    return e
