"""
Deterministic calculators. Every number the assistant states comes from here.

Each function returns a ``Fact``: a short title plus plain-text lines that go
straight into the model's context, and the raw values for tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from racemech.botlib import BotLib, Course

STYLES = ("front", "pace", "late", "end")
STYLE_NAME = {"front": "Front Runner", "pace": "Pace Chaser", "late": "Late Surger", "end": "End Closer"}

ASSUMPTIONS = (
    "Stamina model assumptions: stats by distance type (Sprint/Mile: Speed 1600, Power 1201, Guts 600, "
    "Wit 1200; Medium: 1500/1100/600/1100; Long: 1400/1000/600/1000), Grade A distance aptitude, not rushed, "
    "course slopes and downhill accel savings included. Debuff/recovery sizes are percentages of max HP. "
    "The HP formulas follow umalator's HP calculator."
)


@dataclass
class Fact:
    title: str
    lines: list[str]
    data: dict = field(default_factory=dict)

    def render(self) -> str:
        return f"## {self.title}\n" + "\n".join(f"- {line}" for line in self.lines)


# --------------------------------------------------------------------- skills

def skill_on_course(bl: BotLib, sid: str, course: Course) -> Fact:
    skill = bl.skill(sid)
    entry = skill.entry
    name = skill.name
    if sid.startswith("9"):
        name += " (Inherited)"
    info = bl.describe.describe_skill(sid, entry, name, course.entry, is_cm=course.is_cm)
    rarity = {1: "white (normal)", 2: "gold (rare)", 3: "unique", 4: "unique (evolved)", 5: "unique"}.get(
        entry.get("rarity"), str(entry.get("rarity")))
    lines = [f"Skill id {sid}, rarity: {rarity}", f"Course: {course.display}"]
    if skill.source == "jp":
        lines.insert(0, "JP-ONLY SKILL: not released on Global yet; the name is the Japanese name and "
                        "the data is from the JP version.")
    if skill.description:
        lines.append(f"In-game description: {skill.description}")
    if not info["effect"]:
        lines.append("Cannot activate on this course.")
    else:
        lines += [f"Effect: {e}" for e in info["effects"]]
        lines += [f"Activates: {a}" for a in info["activates"]]
        if info["arms"]:
            lines.append(f"Precondition (must happen first): {info['arms']}")
        if info["timing"]:
            lines.append(f"Timing relative to late-race: {info['timing']}")
        if info["rating"]:
            verdict = _accel_verdict(bl, sid, entry, course)
            lines.append(f"Acceleration rating on this course: {verdict or info['rating']}")
    return Fact(f"Skill: {name}", lines, {"info": info, "sid": sid})


def _accel_verdict(bl: BotLib, sid: str, entry: dict, course: Course) -> str | None:
    """The bot's full verdict sentence (rating, potency, and why it was downgraded)."""
    d = bl.describe
    for alt in entry["alternatives"]:
        cond, pre = alt.get("condition", ""), alt.get("precondition", "")
        if d.evaluate_trigger(cond, pre, course.entry):
            return d.accel_verdict(cond, pre, alt["effects"], course.entry, sid.startswith("9"))
    return None


# -------------------------------------------------------------------- stamina

def _profile(bl: BotLib, style: str, course: Course) -> dict:
    st = bl.stamina
    ground = course.cm.get("ground") if course.cm else None
    gm = st._ground_modifier_for(ground, course.entry.get("surface", 1))
    r = st.compute_stamina(style, course.entry, st._skill_averages, gm)
    coef = st.STRATEGY_COEF_HP[style]
    d = float(course.entry["distance"])
    hp_adj = r["hp_used"] - r["downhill_savings"]
    return {"r": r, "coef": coef, "d": d, "hp_adj": hp_adj, "ground_mod": gm}


def required_stamina(p: dict, net_fraction: float) -> float:
    """Stamina needed for a full last spurt when a net fraction of max HP is lost (+) or gained (-)."""
    return (p["hp_adj"] / (1 - net_fraction) - p["d"]) / (0.8 * p["coef"])


def averages(bl: BotLib) -> dict:
    a = bl.stamina._skill_averages
    return {"gold_debuff": abs(a["gold_debuff"]), "white_debuff": abs(a["white_debuff"]),
            "gold_recovery": a["gold_recovery"], "white_recovery": a["white_recovery"]}


def stamina_baseline(bl: BotLib, course: Course, styles=STYLES) -> Fact:
    lines = [f"Course: {course.display}"]
    data = {}
    for s in styles:
        p = _profile(bl, s, course)
        dh, no_dh = p["r"]["min_stamina_dh"], p["r"]["min_stamina"]
        data[s] = max(dh, 0.0)
        if dh <= 0:
            lines.append(f"{STYLE_NAME[s]}: any Stamina is enough for a full last spurt on this course "
                         "(the course distance alone covers the HP needed), with no debuffs")
        else:
            lines.append(f"{STYLE_NAME[s]}: minimum Stamina for a full last spurt = {dh:.0f} "
                         f"({max(no_dh, 0):.0f} without downhill savings), no debuffs and no recovery skills")
    lines.append(ASSUMPTIONS)
    return Fact("Minimum Stamina for full spurt", lines, data)


def recovery_equivalent(bl: BotLib, course: Course, pct: float, styles=STYLES,
                        stamina: float | None = None) -> Fact:
    """Stamina points worth `pct` (fraction of max HP, e.g. 0.015) per style."""
    lines = [f"Course: {course.display}",
             f"Recovery size: {pct * 100:g}% of max HP"]
    data = {}
    for s in styles:
        p = _profile(bl, s, course)
        ref = stamina if stamina is not None else p["r"]["min_stamina_dh"]
        val = bl.stamina._effective_stamina_delta(pct, ref, p["d"], p["coef"])
        data[s] = val
        lines.append(f"{STYLE_NAME[s]}: {pct * 100:g}% recovery is worth about {val:.0f} Stamina "
                     f"(at a reference of {ref:.0f} Stamina)")
    lines.append("1% of max HP is worth roughly (Stamina + distance / (0.8 x style HP coefficient)) / 100 "
                 "Stamina; values add up linearly for several skills.")
    lines.append(ASSUMPTIONS)
    return Fact("Stamina equivalent of a recovery", lines, data)


def survivable_debuffers(bl: BotLib, course: Course, stamina: float, style: str,
                         recoveries: tuple[float, ...] = (), self_costs: tuple[float, ...] = ()) -> Fact:
    p = _profile(bl, style, course)
    av = averages(bl)
    max_hp = p["d"] + 0.8 * p["coef"] * stamina
    spare = 1 - p["hp_adj"] / max_hp
    budget = spare + sum(recoveries) - sum(self_costs)
    pair = av["gold_debuff"] + av["white_debuff"]
    n_pair, n_gold, n_white = budget / pair, budget / av["gold_debuff"], budget / av["white_debuff"]
    lines = [
        f"Course: {course.display}; running style: {STYLE_NAME[style]}; Stamina {stamina:g}",
        f"Max HP {max_hp:.0f}; HP needed for a full last spurt {p['hp_adj']:.0f}; "
        f"spare HP {spare * 100:.1f}% of max",
    ]
    if recoveries:
        lines.append("Recovery skills counted: " + ", ".join(
            f"{r * 100:g}% of max HP (= {r * max_hp:.0f} HP)" for r in recoveries))
    if self_costs:
        lines.append("Self HP costs counted: " + ", ".join(f"{c * 100:g}%" for c in self_costs))
    whole = max(int(n_pair), 0)
    need_whole = max(required_stamina(p, whole * pair - sum(recoveries) + sum(self_costs)), 0)
    lines += [
        f"A 'debuffer' = one opponent landing 1 gold debuff (avg {av['gold_debuff'] * 100:.2f}%) and "
        f"1 white debuff (avg {av['white_debuff'] * 100:.2f}%) = {pair * 100:.2f}% of max HP",
        f"Survives about {n_pair:.1f} debuffers (gold + white each) -> {whole} whole debuffers; "
        f"{stamina:g} Stamina is {stamina - need_whole:.0f} above the {need_whole:.0f} needed for {whole}",
        f"If debuffers only land gold debuffs: about {n_gold:.1f}",
        "Stamina needed for N debuffers (gold + white each): "
        + ", ".join(f"{n}: {max(required_stamina(p, n * pair - sum(recoveries) + sum(self_costs)), 0):.0f}"
                    for n in range(0, 6)),
        ASSUMPTIONS,
    ]
    return Fact("Debuffers survivable", lines, {"pair": n_pair, "gold": n_gold, "white": n_white,
                                                 "spare": spare})
