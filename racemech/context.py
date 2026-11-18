"""
Turn a question into the context the model answers from: calculator results (every number)
plus retrieved knowledge passages. Pure code; no model involved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from racemech import calculators as calc
from racemech.botlib import BotLib, Course
from racemech.entities import WHITE_RECOVERY, Entities, SkillMatcher, extract
from racemech.retrieval import BM25, Doc

MAX_SKILLS = 5
_STAMINA_WORDS = re.compile(
    r"\b(stamina|stam|survive|debuff|debuffer|debuffers|hp|recovery|heal|spurt)\b", re.I)
_WORTH_WORDS = re.compile(r"\b(worth|equivalent|equal|equals|value|how much)\b", re.I)
_WIT_WORDS = re.compile(r"\b(wit|wits|wis|wisdom|int|intelligence|downhills?)\b", re.I)
_POWER_WORDS = re.compile(r"\b(power|pow|pwr|uphills?|hills?|slopes?)\b", re.I)


@dataclass
class Context:
    question: str
    entities: Entities
    course: Course | None
    facts: list[calc.Fact] = field(default_factory=list)
    passages: list[tuple[float, Doc]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        parts = []
        if self.notes:
            parts.append("# Notes about the question\n" + "\n".join(f"- {n}" for n in self.notes))
        if self.facts:
            facts = "\n\n".join(f.render() for f in self.facts)
            parts.append("# Computed facts (exact; use these numbers)\n\n" + facts)
        if self.passages:
            parts.append("# Reference passages\n\n" + "\n\n".join(
                f"## {d.title} [{d.source}]\n{d.text}" for _, d in self.passages))
        if not parts:
            return "# No relevant information was found for this question."
        return "\n\n".join(parts)


def _effects(entry: dict) -> list[dict]:
    alts = entry.get("alternatives") or [{}]
    return alts[0].get("effects", [])


class ContextBuilder:
    def __init__(self, bl: BotLib, index: BM25, k: int = 5):
        self.bl, self.index, self.k = bl, index, k
        self.matcher = SkillMatcher(bl.game.skills)

    def _active(self, sid: str, course: Course) -> bool:
        return bool(calc.skill_on_course(self.bl, sid, course).data["info"]["effect"])

    def _classify(self, ent: Entities, course: Course | None):
        """Split matched skills into greens (owned Stamina), recoveries and debuffs, as HP items."""
        greens, recoveries, candidates, debuffs = [], [], [], []
        for sm in ent.skills:
            name = self.bl.skill_name(sm.sid)
            for e in _effects(self.bl.skill(sm.sid).entry):
                typ, tgt, mod = e["type"], e["target"], e["modifier"]
                if typ == 2 and tgt in (1, 2) and mod > 0:
                    if course is not None and not self._active(sm.sid, course):
                        ent.notes.append(f"{name} does not activate on {course.display}, so its Stamina "
                                         "was not counted.")
                        continue
                    item = calc.HPItem(name, mod / 10000, sm.count)
                    (candidates if sm.role == "candidate" else greens).append(item)
                elif typ == 9 and tgt in (1, 2) and mod > 0:
                    item = calc.HPItem(name, mod / 10000, sm.count)
                    (candidates if sm.role == "candidate" else recoveries).append(item)
                elif typ == 9 and tgt not in (1, 2) and mod < 0:
                    sm.role = "opponent"
                    debuffs.append(calc.HPItem(name, -mod / 10000, sm.count))
        for r in ent.recoveries:
            label = "white recovery" if r == WHITE_RECOVERY else f"{r * 100:g}% recovery"
            recoveries.append(calc.HPItem(label, r))
        for r in ent.candidate_recoveries:
            candidates.append(calc.HPItem("a white recovery" if r == WHITE_RECOVERY
                                          else f"a {r * 100:g}% recovery", r))
        return greens, recoveries, [c for c in candidates if c.label], debuffs

    def build(self, question: str) -> Context:
        ent = extract(question, self.matcher)
        ctx = Context(question, ent, None, notes=list(ent.notes))

        number = ent.cm
        if number is None:
            number = self.bl.current_cm_number()
            if number is not None:
                ctx.notes.append(f"No CM was named; using the current/next Champions Meeting, CM#{number}.")
        if number is not None:
            ctx.course = self.bl.course_for_cm(number)
            if ctx.course is None:
                ctx.notes.append(f"CM#{number} is not in the game data (not released yet or unknown), so no "
                                 "course-specific numbers are available for it.")
        course = ctx.course

        greens, recoveries, candidates, debuffs = self._classify(ent, course)
        ctx.notes += [n for n in ent.notes if n not in ctx.notes]
        for sm in ent.skills[:MAX_SKILLS]:
            if course is not None and sm.role != "opponent":
                ctx.facts.append(calc.skill_on_course(self.bl, sm.sid, course))

        if ent.debuffers:
            av = calc.averages(self.bl)
            debuffs.append(calc.HPItem("debuffer (1 gold + 1 white debuff, average)",
                                       av["gold_debuff"] + av["white_debuff"], ent.debuffers))

        wants_stamina = bool(_STAMINA_WORDS.search(question) or ent.stamina or ent.debuffers or debuffs)
        if course is not None and wants_stamina:
            styles = tuple(ent.styles) or calc.STYLES
            if ent.stamina is not None:
                for s in styles:
                    ctx.facts.append(calc.stamina_plan(self.bl, course, s, ent.stamina, greens, recoveries,
                                                       candidates, debuffs))
                    if ent.asks_how_many or not (debuffs or candidates):
                        owned = tuple(r.pct * r.count for r in recoveries)
                        ctx.facts.append(calc.survivable_debuffers(
                            self.bl, course, ent.stamina + sum(g.pct * g.count for g in greens), s,
                            recoveries=owned))
            else:
                ctx.facts.append(calc.stamina_baseline(self.bl, course, styles))
                all_rec = [r.pct for r in recoveries + candidates]
                if all_rec and (_WORTH_WORDS.search(question) or not debuffs):
                    for r in dict.fromkeys(all_rec):
                        ctx.facts.append(calc.recovery_equivalent(self.bl, course, r, styles))
            if ent.stamina is not None and (recoveries or candidates) and _WORTH_WORDS.search(question):
                for r in dict.fromkeys(x.pct for x in recoveries + candidates):
                    ctx.facts.append(calc.recovery_equivalent(self.bl, course, r, styles, ent.stamina))

        if course is not None and (ent.wit is not None or _WIT_WORDS.search(question)):
            wit_fact = calc.wit_on_course(self.bl, course, ent.wit, tuple(ent.styles) or calc.STYLES)
            title = "KEY POINTS for Wit on this course (the answer must state each one)"
            ctx.facts.insert(0, calc.Fact(title, wit_fact.data["summary_points"]))
            ctx.facts.append(wit_fact)
        if course is not None and (ent.power is not None or _POWER_WORDS.search(question)):
            ctx.facts.append(calc.power_on_course(self.bl, course, ent.power))

        ctx.passages = self.index.search(question, self.k)
        return ctx
