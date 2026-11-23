"""
Keyword retrieval (BM25) over the knowledge pack. Fully local, no model, deterministic.

Documents are the ``## `` sections of ``racemech/knowledge/*.md`` plus, when available, one
document per field of the condition-field reference (read from the bot checkout at runtime;
that text is community-written, so it is not shipped in this repo).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
CONDITION_REFERENCE = Path("tests") / "skill_condition_explanation.txt"   # relative to the bot repo

_STOP = set("""a an and are as at be by can do does for from has have how i if in into is it its of on or
so that the their them then there these this to was what when where which who why will with would you
your about any my me""".split())


# Community shorthand -> the word the knowledge pack uses. Applied to documents and queries alike.
_ALIASES = {
    "accel": "acceleration", "accels": "acceleration", "velocity": "speed", "spd": "speed",
    "stam": "stamina", "sta": "stamina", "wiz": "wit", "wis": "wit", "wisdom": "wit", "pow": "power",
    "pwr": "power", "heal": "recovery", "heals": "recovery", "recover": "recovery", "kakari": "rushed",
    "rush": "rushed", "additive": "stack", "multiplicative": "stack", "multiply": "stack",
    "combine": "stack", "stacking": "stack", "stacks": "stack", "last": "duration", "lasts": "duration",
    "lane": "lane", "dueling": "showdown", "duel": "showdown", "oonige": "runaway", "nige": "front",
    "debuffs": "debuff", "uma": "runner", "umas": "runner",
}


def tokenize(text: str) -> list[str]:
    out = []
    for raw in re.findall(r"[a-z0-9_]+", text.lower()):
        parts = [raw] + ([p for p in raw.split("_") if p] if "_" in raw else [])
        for t in parts:
            t = _ALIASES.get(t, t)
            if t in _STOP or len(t) < 2:
                continue
            if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
                t = t[:-1]
            out.append(t)
    return out


@dataclass
class Doc:
    source: str
    title: str
    text: str


def load_markdown_sections(directory: Path = KNOWLEDGE_DIR) -> list[Doc]:
    docs = []
    for path in sorted(directory.glob("*.md")):
        title, buf = None, []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## ") or line.startswith("# "):     # a top-level heading ends a section
                if title:
                    docs.append(Doc(path.stem, title, "\n".join(buf).strip()))
                title, buf = (line[3:].strip() if line.startswith("## ") else None), []
            elif title:
                buf.append(line)
        if title:
            docs.append(Doc(path.stem, title, "\n".join(buf).strip()))
    return docs


def load_condition_reference(bot_repo: Path) -> list[Doc]:
    """One doc per condition field: a bare `field_name` line followed by its description."""
    path = Path(bot_repo) / CONDITION_REFERENCE
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    docs, field, buf = [], None, []
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if re.fullmatch(r"[a-z0-9_]+", line.strip()) and nxt and not re.fullmatch(r"[a-z0-9_]+", nxt.strip()):
            if field:
                docs.append(Doc("conditions", f"Condition field {field}", "\n".join(buf).strip()))
            field, buf = line.strip(), []
        elif field:
            buf.append(line)
    if field:
        docs.append(Doc("conditions", f"Condition field {field}", "\n".join(buf).strip()))
    return docs


class BM25:
    def __init__(self, docs: list[Doc], k1: float = 1.4, b: float = 0.75, title_boost: int = 3):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tfs = [Counter(tokenize(d.title) * title_boost + tokenize(d.text)) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avg = sum(self.lens) / max(len(self.lens), 1)
        df = Counter(t for tf in self.tfs for t in tf)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, k: int = 4) -> list[tuple[float, Doc]]:
        q = tokenize(query)
        scored = []
        for doc, tf, length in zip(self.docs, self.tfs, self.lens, strict=True):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    norm = self.k1 * (1 - self.b + self.b * length / self.avg)
                    s += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            if s > 0:
                scored.append((s, doc))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]


def build_index(bot_repo: Path | None = None, exclude: frozenset[str] = frozenset()) -> BM25:
    docs = [d for d in load_markdown_sections() if d.source not in exclude]
    if bot_repo is not None:
        docs += load_condition_reference(bot_repo)
    return BM25(docs)
