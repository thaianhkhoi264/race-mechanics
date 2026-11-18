"""
Turn a question into the context the model answers from: calculator results (every number)
plus retrieved knowledge passages. Pure code; no model involved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from racemech import calculators as calc
from racemech.botlib import BotLib, Course
from racemech.entities import Entities, SkillMatcher, extract
from racemech.retrieval import BM25, Doc

MAX_SKILLS = 4
_STAMINA_WORDS = re.compile(
    r"\b(stamina|stam|survive|debuff|debuffer|debuffers|hp|recovery|heal|spurt)\b", re.I)
_WORTH_WORDS = re.compile(r"\b(worth|equivalent|equal|equals|value|how much)\b", re.I)


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


class ContextBuilder:
    def __init__(self, bl: BotLib, index: BM25, k: int = 5):
        self.bl, self.index, self.k = bl, index, k
        self.matcher = SkillMatcher(bl.game.skills)

    def _recovery_from_skill(self, sid: str) -> float | None:
        entry = self.bl.skill(sid).entry
        for alt in entry["alternatives"][:1]:
            for e in alt["effects"]:
                if e["type"] == 9 and e["target"] in (1, 2) and e["modifier"] > 0:
                    return e["modifier"] / 10000
        return None

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
        for sm in ent.skills[:MAX_SKILLS]:
            if course is not None:
                ctx.facts.append(calc.skill_on_course(self.bl, sm.sid, course))
            if sm.score < 100:
                ctx.notes.append(f'"{sm.matched}" was read as the skill {sm.name}.')

        recoveries = list(ent.recoveries)
        for sm in ent.skills:
            r = self._recovery_from_skill(sm.sid)
            if r:
                recoveries.append(r)

        wants_stamina = bool(_STAMINA_WORDS.search(question) or ent.stamina or ent.debuffers)
        if course is not None and wants_stamina:
            styles = tuple(ent.styles) or calc.STYLES
            if ent.stamina is not None:
                for s in styles:
                    ctx.facts.append(calc.survivable_debuffers(self.bl, course, ent.stamina, s,
                                                               recoveries=tuple(recoveries)))
            else:
                ctx.facts.append(calc.stamina_baseline(self.bl, course, styles))
            if recoveries and (_WORTH_WORDS.search(question) or ent.stamina is None):
                for r in dict.fromkeys(recoveries):
                    ctx.facts.append(calc.recovery_equivalent(self.bl, course, r, styles, ent.stamina))

        ctx.passages = self.index.search(question, self.k)
        return ctx
