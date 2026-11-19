"""Facts about a character on a course: aptitudes, how to run her, and Stamina with her own recoveries."""
from __future__ import annotations

from racemech import calculators as calc
from racemech.botlib import BotLib, Course
from racemech.characters import (
    DISTANCE_TYPES,
    STYLE_NAME,
    CharacterMatch,
    Recovery,
    course_recoveries,
    skill_distances,
    skill_styles,
    style_verdict,
)

_DIST_NAME = {"sprint": "Sprint", "mile": "Mile", "medium": "Medium", "long": "Long"}


def _skill_tag(bl: BotLib, sid: str) -> str:
    entry = bl.skill(sid).entry
    bits = [STYLE_NAME[s] for s in sorted(skill_styles(entry))]
    bits += [f"{_DIST_NAME[d]} only" for d in sorted(skill_distances(entry))]
    return f"{bl.skill_name(sid)} ({', '.join(bits)})" if bits else bl.skill_name(sid)


def character_profile(bl: BotLib, m: CharacterMatch, course: Course | None,
                      asked_style: str | None) -> calc.Fact:
    c = m.card
    v = style_verdict(c, bl.game.skills)
    lines = [
        f"Character: {m.display}, {c.title} (card {c.card_id})",
        "Aptitudes: distance " + ", ".join(f"{_DIST_NAME[k]} {g}" for k, g in c.distance.items())
        + "; running style " + ", ".join(f"{STYLE_NAME[k]} {g}" for k, g in c.style.items())
        + "; ground " + ", ".join(f"{k.title()} {g}" for k, g in c.ground.items()),
    ]
    if course is not None:
        dist = DISTANCE_TYPES.get(course.entry.get("distanceType"), "medium")
        surface = "turf" if course.entry.get("surface", 1) == 1 else "dirt"
        lines.append(f"Course fit for {course.display}: {_DIST_NAME[dist]} {c.distance[dist]}, "
                     f"{surface.title()} {c.ground[surface]}")
    if c.unique and bl.skill(c.unique):
        lines.append(f"Unique skill: {_skill_tag(bl, c.unique)}")
    start = [_skill_tag(bl, s) for s, lv in c.built_in if lv == 0 and bl.skill(s)]
    later = [f"{_skill_tag(bl, s)} at potential {lv}" for s, lv in c.built_in if lv > 0 and bl.skill(s)]
    lines.append("Built-in skills (learnable in her career): " + "; ".join(start + later))
    votes = ", ".join(f"{STYLE_NAME[s]} {n}" for s, n in v["votes"].items() if n)
    best = ", ".join(f"{STYLE_NAME[s]} {c.style[s]}" for s in v["candidates"])
    if v["dominant"]:
        verdict = (f"run her as a {STYLE_NAME[v['dominant']]}: best aptitude ({best}) and her own skills "
                   f"favour it (style-locked skills: {votes or 'none'})")
    else:
        verdict = (f"no single best style: equal best aptitude in {best}; her style-locked skills are split "
                   f"({votes or 'none'}), so answer for each of those styles")
    if c.default_style:
        verdict += f". The game's default style for her is {STYLE_NAME[c.default_style]}"
    lines.append(f"STYLE VERDICT: {verdict}.")
    if asked_style and asked_style in STYLE_NAME and c.style[asked_style] not in "SA":
        lines.append(f"Note: the question asks about her as a {STYLE_NAME[asked_style]}, where her "
                     f"aptitude is only {c.style[asked_style]}.")
    return calc.Fact("Character (from the Global game data)", lines,
                     {"verdict": v, "card_id": c.card_id})


def _status_text(r: Recovery) -> str:
    return {"fires": "always fires", "likely": "likely to fire", "possible": "may fire",
            "unlikely": "unlikely to fire", "no": "does not fire here"}[r.status]


def character_stamina(bl: BotLib, m: CharacterMatch, course: Course, style: str,
                      debuff_fraction: float = 0.0) -> calc.Fact:
    """Minimum Stamina for a full last spurt with her own recoveries counted step by step."""
    activates = {}
    for sid in [m.card.unique] + [s for s, _ in m.card.built_in]:
        if sid and bl.skill(sid):
            fact = calc.skill_on_course(bl, sid, course)
            line = next((ln for ln in fact.lines if ln.startswith("Activates:")), None)
            if line:
                activates[sid] = line.removeprefix("Activates: ")
    recs = course_recoveries(m.card, bl.game.skills, course.entry.get("distanceType", 3), style, activates)
    p = calc._profile(bl, style, course)
    need = lambda heal: max(calc.required_stamina(p, debuff_fraction - heal), 0.0)  # noqa: E731
    base = need(0.0)
    lines = [f"{m.display} as a {STYLE_NAME[style]} on {course.display}"
             + (f", with {debuff_fraction * 100:.2f}% of max HP lost to debuffs" if debuff_fraction else "")]
    lines.append(f"Minimum Stamina for a full last spurt with none of her recoveries: {base:.0f}")
    usable = [r for r in recs if r.status != "no"]
    for r in recs:
        tail = "" if r.status == "no" else f"; on its own it lowers the need to {need(r.pct):.0f}"
        own = "she always has it" if r.kind == "unique" else "must be bought in her career"
        lines.append(f"{r.name} ({r.kind}, restores {r.pct * 100:g}% of max HP, {own}): "
                     f"{_status_text(r)} - {r.reason}{tail}")
    if not recs:
        lines.append("Her unique and built-in skills include no HP recovery.")
    likely = [r for r in usable if r.status in ("fires", "likely")]
    if usable:
        lines.append(f"With every recovery above that can fire: {need(sum(r.pct for r in usable)):.0f}")
    if likely:
        target = need(sum(r.pct for r in likely))
        names = ", ".join(r.name for r in likely)
        rec = (f"aim for about {target:.0f} Stamina counting only the recoveries likely to fire ({names}); "
               f"{base:.0f} if you want to be safe even when none of them fire")
    else:
        rec = f"aim for about {base:.0f} Stamina; none of her own recoveries can be relied on here"
    lines.append(f"RECOMMENDATION as a {STYLE_NAME[style]}: {rec}.")
    lines.append(calc.ASSUMPTIONS + " Typical placings by style (Front 1st-2nd, Pace 2nd-4th, Late 4th-7th, "
                 "End 6th-9th of 9) are an assumption used only to judge position-gated recoveries.")
    return calc.Fact(f"Stamina for {m.display} as a {STYLE_NAME[style]} (precomputed)", lines,
                     {"base": base, "recoveries": recs})
