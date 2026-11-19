"""
Deterministic calculators. Every number the assistant states comes from here.

Each function returns a ``Fact``: a short title plus plain-text lines that go
straight into the model's context, and the raw values for tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from racemech import stats
from racemech.activation import blockers
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

_HP_EFFECT = re.compile(r"HP Recovery ([+-])(\d*\.?\d+)( on other runners)?")


def clear_effect(text: str) -> str:
    """'HP Recovery +0.055' -> 'restores 5.5% of max HP'; label effect type 35."""
    def hp(m: re.Match) -> str:
        pct = f"{float(m[2]) * 100:g}% of max HP"
        if m[3]:
            return f"drains {pct} from other runners" if m[1] == "-" else f"restores {pct} to other runners"
        return f"restores {pct}" if m[1] == "+" else f"costs {pct}"
    text = _HP_EFFECT.sub(hp, text)
    lane = "target lane shift (moves her aim sideways to get clear; inferred from the skill text)"
    return re.sub(r"Effect type 35 [+-]?\d*\.?\d+", lane, text)


def skill_on_course(bl: BotLib, sid: str, course: Course, style: str | None = None) -> Fact:
    """``style``: the asker's running style, if known; a skill locked to another style is flagged."""
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
    tracks = bl.game.track_names
    course_block = blockers(entry, course, tracks)
    if not info["effect"] or course_block:
        why = "; ".join(course_block) if course_block else "its conditions can't be met here"
        lines.append(f"CANNOT ACTIVATE on this course: {why}.")
    else:
        style_block = blockers(entry, course, tracks, style) if style else []
        if style_block:
            lines.append(f"STYLE MISMATCH: {'; '.join(style_block)}. It cannot activate for this runner, "
                         "so it is useless for her whatever its rating.")
        lines += [f"Effect: {clear_effect(e)}" for e in info["effects"]]
        lines += [f"Activates: {_clear_activates(a)}" for a in info["activates"]]
        if info["arms"]:
            lines.append(f"Precondition (must happen first): {info['arms']}")
        whole_race = all(a.startswith("Whenever its conditions are met —") or "(0–" in a
                         for a in info["activates"]) and "late-race" not in " ".join(info["activates"])
        if info["timing"] and not whole_race:
            lines.append(f"Timing: {clear_timing(info['timing'])}")
        if style_block:
            lines.append("OVERALL RATING for this runner: USELESS (wrong running style).")
        elif info["rating"]:
            lines.append(_rating_line(_accel_verdict(bl, sid, entry, course) or info["rating"]))
    return Fact(f"Skill: {name}", lines, {"info": info, "sid": sid, "blocked": course_block})


_TIMING = re.compile(r"^(?P<lead>.*?) (?P<off>[\d,]+) m (?P<dir>before late-race|after late-race starts) "
                     r"\((?P<p2>[\d,]+) m\)$")


def clear_timing(text: str) -> str:
    """
    Reword the bot's timing note so a small model can't misread the bracketed number as an offset:
    "Activates 250 m before late-race (800 m)" ->
    "late-race starts at 800 m; activates 250 m before that point".
    """
    m = _TIMING.match(text)
    if m:
        where = "before that point" if m["dir"].startswith("before") else "after that point"
        return f"late-race starts at {m['p2']} m; {m['lead'].lower()} {m['off']} m {where}"
    m = re.match(r"^(.*?) \(([\d,]+) m\)$", text)
    if m:
        return f"{m[1]} (late-race starts at {m[2]} m)"
    return text


_CORNER_RANDOM = re.compile(
    r"^Whenever its conditions are met \(([^)]*)\)(.*?)(?: — |, )?also `corner_random==(\d)`$")


_TO_FINISH = re.compile(r"\(([\d,]+)\s*[-–]\s*([\d,]+) m to the finish\)")


def _clear_activates(text: str) -> str:
    """Reword raw tokens the bot's describer leaves in (it doesn't map corner_random yet), and
    "(1,099–1,600 m to the finish)", which reads like a distance from the finish line."""
    text = _TO_FINISH.sub(lambda m: f"(from the {m[1]} m mark to the finish line at {m[2]} m)", text)
    m = _CORNER_RANDOM.match(text)
    if m:
        n = int(m[3])
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n, "th")
        return f"At a random point on the track's {n}{suffix} corner ({m[1]}){m[2]}"
    return text


def _rating_line(verdict: str) -> str:
    """
    Split the bot's verdict ("Bad inherited accel, high acceleration, but activates too early, requires ...")
    into labelled parts so the overall rating can't be confused with the size word.
    """
    parts = [x.strip() for x in verdict.split(", ")]
    rating = parts[0]
    size = parts[1] if len(parts) > 1 else ""
    rest = ", ".join(parts[2:]).removeprefix("but ").strip()
    word = rating.split()[0].upper()
    out = f"OVERALL RATING on this course: {word} ({rating})"
    if size:
        out += f". Raw size of the boost: {size} (this is not the rating)"
    if rest:
        out += f". Why / requirements: {rest}"
    return out


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


@dataclass
class HPItem:
    label: str
    pct: float          # fraction of max HP
    count: int = 1


def _verdict(margin: float) -> str:
    if margin >= 15:
        return f"survives the full last spurt with about {margin:.0f} Stamina to spare"
    if abs(margin) < 1:
        return ("is borderline: exactly at the requirement, so any extra debuff or missed skill "
                "means running out")
    if margin >= -15:
        return (f"is borderline: {abs(margin):.0f} Stamina {'above' if margin >= 0 else 'below'} the "
                "requirement, so it just barely makes it or just barely runs out")
    return f"does NOT have enough: about {-margin:.0f} Stamina short of a full last spurt"


def stamina_plan(bl: BotLib, course: Course, style: str, stamina: float,
                 greens: list[HPItem] | None = None, recoveries: list[HPItem] | None = None,
                 candidates: list[HPItem] | None = None, debuffs: list[HPItem] | None = None) -> Fact:
    """
    Answer "is this Stamina enough?" with everything the player listed: green Stamina skills
    (flat Stamina, label + Stamina in pct field), owned recoveries, recoveries being considered,
    and debuffs expected from opponents. The verdict is computed here, not by the model.
    """
    greens, recoveries, candidates, debuffs = greens or [], recoveries or [], candidates or [], debuffs or []
    p = _profile(bl, style, course)
    green_total = sum(g.pct * g.count for g in greens)
    effective = stamina + green_total
    debuff_load = sum(d.pct * d.count for d in debuffs)
    owned = sum(r.pct * r.count for r in recoveries)
    need = max(required_stamina(p, debuff_load - owned), 0)

    lines = [f"Course: {course.display}; running style: {STYLE_NAME[style]}"]
    if greens:
        lines.append(f"Effective Stamina: {stamina:g} + " + " + ".join(
            f"{g.pct * g.count:g} ({g.label})" for g in greens) + f" = {effective:g}")
    else:
        lines.append(f"Effective Stamina: {effective:g}")
    lines.append("Debuffs expected: " + (", ".join(
        f"{d.count} x {d.label} ({d.pct * 100:.2f}% of max HP each)" for d in debuffs) if debuffs else "none")
        + "; recoveries counted: " + (", ".join(
            f"{r.count} x {r.label} ({r.pct * 100:g}%)" for r in recoveries) if recoveries else "none"))
    lines.append(f"Stamina needed for a full last spurt in this situation: {need:.0f}")
    source = f" ({stamina:g} + {green_total:g} from green skills)" if greens else ""
    lines.append(f"VERDICT: effective Stamina {effective:g}{source} vs {need:.0f} needed -> the runner "
                 f"{_verdict(effective - need)}.")
    data = {"effective": effective, "need": need, "margin": effective - need}

    if candidates:
        with_c = owned + sum(c.pct * c.count for c in candidates)
        need_c = max(required_stamina(p, debuff_load - with_c), 0)
        label = " + ".join(f"{c.label} ({c.pct * 100:g}%)" for c in candidates)
        gain = need - need_c
        lines.append(f"WITH {label.upper()}: Stamina needed drops from {need:.0f} to {need_c:.0f} "
                     f"(worth about {gain:.0f} Stamina), so the runner {_verdict(effective - need_c)}.")
        before, after = effective - need, effective - need_c
        if before >= 15:
            rec = f"not needed: the runner already has enough without {label}; it only adds a safety margin"
        elif after >= -1:
            rec = f"yes, get {label}: without it the runner is short or borderline, with it she makes it"
        else:
            rec = (f"{label} alone is NOT enough: even with it the runner is still about {-after:.0f} "
                   "Stamina short, so more Stamina or more recovery is needed")
        lines.append(f"RECOMMENDATION: {rec}.")
        data |= {"need_with_candidates": need_c, "margin_with_candidates": after}
    lines.append(ASSUMPTIONS)
    return Fact("Is this Stamina enough? (precomputed verdict)", lines, data)


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
    lines.append(f"A 'debuffer' = one opponent landing 1 gold debuff (avg {av['gold_debuff'] * 100:.2f}%) "
                 f"and 1 white debuff (avg {av['white_debuff'] * 100:.2f}%) = {pair * 100:.2f}% of max HP")
    if budget < 0:
        need0 = max(required_stamina(p, -sum(recoveries) + sum(self_costs)), 0)
        lines.append(f"Survives 0 debuffers: even with no debuffs at all, {stamina:g} Stamina is about "
                     f"{need0 - stamina:.0f} short of the {need0:.0f} needed for a full last spurt")
    else:
        whole = int(n_pair)
        need_whole = max(required_stamina(p, whole * pair - sum(recoveries) + sum(self_costs)), 0)
        lines += [
            f"Survives about {n_pair:.1f} debuffers (gold + white each) -> {whole} whole debuffers; "
            f"{stamina:g} Stamina is {stamina - need_whole:.0f} above the {need_whole:.0f} "
            f"needed for {whole}",
            f"If debuffers only land gold debuffs: about {n_gold:.1f}",
        ]
    lines += [
        "Stamina needed for N debuffers (gold + white each): "
        + ", ".join(f"{n}: {max(required_stamina(p, n * pair - sum(recoveries) + sum(self_costs)), 0):.0f}"
                    for n in range(0, 6)),
        ASSUMPTIONS,
    ]
    return Fact("Debuffers survivable", lines, {"pair": n_pair, "gold": n_gold, "white": n_white,
                                                 "spare": spare})


# ---------------------------------------------------------------- Wit / Power

def _levels(given: float | None, defaults: tuple[float, ...]) -> list[float]:
    if given is None:
        return list(defaults)
    return [given] + [d for d in (1200.0,) if d != given]


def _slopes(course: Course) -> tuple[list[dict], list[dict]]:
    slopes = [s for s in course.entry.get("slopes", []) if s.get("slope")]
    return [s for s in slopes if s["slope"] > 0], [s for s in slopes if s["slope"] < 0]


def _hill(s: dict) -> str:
    return f"{s['start']:.0f}-{s['start'] + s['length']:.0f} m ({abs(s['slope']) / stats.SLOPE_SCALE:g}%)"


def wit_on_course(bl: BotLib, course: Course, wit: float | None = None,
                  styles: tuple[str, ...] = STYLES) -> Fact:
    """What Wit does on this course, at the given Wit or at 600/900/1200 for comparison."""
    d = float(course.entry["distance"])
    pk_end = d * 10 / 24
    _, down = _slopes(course)
    down_m = sum(s["length"] for s in down)
    lines = [f"Course: {course.display}",
             f"Position keeping (pace-up / pace-down, Front Runner speed-up) runs in sections 1-10 = "
             f"0-{pk_end:.0f} m of this {d:.0f} m course."]
    data: dict = {"pk_end": pk_end, "downhill_m": down_m, "levels": {}}
    for w in _levels(wit, (600.0, 1200.0)):
        lo, hi = stats.section_random_pct(w)
        row = {"activation": stats.skill_activation_pct(w), "rushed": stats.rushed_pct(w),
               "pace_up": stats.pace_up_check_pct(w), "front": stats.front_check_pct(w),
               "random": (lo, hi), "downhill_share": stats.downhill_mode_share(w)}
        data["levels"][w] = row
        lines.append(
            f"At {w:g} Wit: skill activation {row['activation']:.1f}%; rushed chance {row['rushed']:.0f}%; "
            f"pace-up check {row['pace_up']:.1f}% (Front Runner speed-up/overtake {row['front']:.1f}%) "
            f"every 2 s; random speed per section {lo:+.3f}% to {hi:+.3f}% of base speed"
            + (f"; downhill accel mode entry chance {w * 0.04:.0f}% per second, in the mode "
               f"{row['downhill_share'] * 100:.1f}% of downhill time" if down else ""))
    if down:
        lines.append(f"Downhills: {', '.join(_hill(s) for s in down)} = {down_m:.0f} m in total.")
        v = stats.base_speed(d)
        gains = {w: stats.downhill_gain_m(down, w, v) for w in data["levels"]}
        data["gain_m"] = gains
        lines.append("Distance gained from downhill accel mode speed (+0.3 + slope%/10 m/s while in it): "
                     + "; ".join(f"{w:g} Wit about {g:.1f} m ({g / 2.5:.1f} lengths)"
                                 for w, g in gains.items()))
        for s in styles:
            p = _profile(bl, s, course)
            base_rate = p["r"].get("downhill_mode_rate") or 0
            if not base_rate:
                continue
            parts, eq = [], {}
            for w in data["levels"]:
                saved = p["r"]["downhill_savings"] * stats.downhill_mode_share(w) / base_rate
                eq[w] = saved / (0.8 * p["coef"])
                parts.append(f"{w:g} Wit saves {saved:.0f} HP (= {eq[w]:.0f} Stamina)")
            data.setdefault("stamina_eq", {})[s] = eq
            data.setdefault("need", {})[s] = {w: max(p["r"]["min_stamina"] - eq[w], 0.0) for w in eq}
            lines.append(f"{STYLE_NAME[s]} downhill HP saved: " + "; ".join(parts))
        base_wit = bl.stamina.DISTANCE_STATS.get(course.entry.get("distanceType", 3),
                                                 bl.stamina.DISTANCE_STATS[3])["wit"]
        lines.append(f"HP saved is compared with never entering downhill accel mode. The minimum-Stamina "
                     f"figures elsewhere already assume {base_wit} Wit on this course.")
    else:
        lines.append("This course has no downhills, so Wit gives no downhill HP savings here.")
    lines.append("Wit check values use Strategy aptitude A; skill activation uses base Wit.")
    general = ("skill activation, rushed chance, position keeping checks and section randomness work "
               "the same on every course")
    eqs = data.get("stamina_eq")
    if eqs:
        who = STYLE_NAME[next(iter(eqs))] if len(eqs) == 1 else "depending on running style"

        def span(w: float) -> str:
            vals = [e[w] for e in eqs.values()]
            lo, hi = min(vals), max(vals)
            return f"{lo:.0f}" if round(lo) == round(hi) else f"{lo:.0f}-{hi:.0f}"
        ws = sorted(data["levels"])
        g = data["gain_m"]
        share = down_m / d
        top_lengths = g[ws[-1]] / 2.5
        weight = "a lot" if top_lengths >= 3.5 else ("noticeably" if top_lengths >= 1.5 else "a little")
        worst = max(n[ws[0]] for n in data["need"].values())
        if worst < 400:
            kind = {1: "a Sprint race", 2: "a Mile race"}.get(course.entry.get("distanceType"), "this race")
            stam = (f"Stamina is not a concern here ({kind}): even at {ws[0]:g} Wit the minimum Stamina for "
                    f"a full last spurt is only about {worst:.0f}, so the HP the downhills save (worth "
                    f"{span(ws[0])} Stamina at {ws[0]:g} Wit, {who}) matters little.")
        else:
            best = max(n[ws[-1]] for n in data["need"].values())
            stam = (f"It also saves HP worth {span(ws[0])} Stamina at {ws[0]:g} Wit and {span(ws[-1])} "
                    f"Stamina at {ws[-1]:g} Wit ({who}), which lowers the minimum Stamina for a full last "
                    f"spurt from about {worst:.0f} to {best:.0f} (highest running style).")
        points = [f"SUMMARY: Wit matters {weight} on this course because {down_m:.0f} m "
                  f"({share * 100:.0f}% of the race) is downhill. Downhill accel mode gains about "
                  f"{g[ws[0]]:.1f} m ({g[ws[0]] / 2.5:.1f} lengths) at {ws[0]:g} Wit and {g[ws[-1]]:.1f} m "
                  f"({g[ws[-1]] / 2.5:.1f} lengths) at {ws[-1]:g} Wit.",
                  f"STAMINA: {stam}",
                  f"Otherwise {general}."]
    else:
        points = ["SUMMARY: this course has no downhills, so nothing about Wit is course-specific; "
                  f"{general}."]
    data["summary_points"] = points
    data["summary"] = " ".join(points)
    return Fact("What Wit does on this course (computed)", lines, data)


def power_on_course(bl: BotLib, course: Course, power: float | None = None) -> Fact:
    """Uphill slowdown on this course for the given Power, or 800/1000/1200 for comparison."""
    d = float(course.entry["distance"])
    up, _ = _slopes(course)
    v = stats.base_speed(d)
    lines = [f"Course: {course.display}"]
    data: dict = {"uphill_m": sum(s["length"] for s in up), "levels": {}}
    if not up:
        lines.append("This course has no uphills, so Power does not reduce any hill slowdown here; "
                     "Power still sets acceleration and lane-change speed.")
        return Fact("What Power does on this course (computed)", lines, data)
    lines.append(f"Uphills: {', '.join(_hill(s) for s in up)} = {data['uphill_m']:.0f} m in total "
                 f"(base speed on this course {v:.1f} m/s).")
    for pw in _levels(power, (800.0, 1000.0, 1200.0)):
        parts, lost = [], 0.0
        for s in up:
            loss = stats.uphill_loss(s["slope"], pw)
            lost += s["length"] / v * loss
            parts.append(f"-{loss:.3f} m/s on {s['start']:.0f}-{s['start'] + s['length']:.0f} m")
        data["levels"][pw] = lost
        lines.append(f"At {pw:g} Power: " + "; ".join(parts)
                     + f"; about {lost:.1f} m lost over all uphills ({lost / 2.5:.2f} lengths)")
    lines.append("Distance lost = time on the hill x speed loss (an estimate; acceleration not modelled).")
    return Fact("What Power does on this course (computed)", lines, data)


# ------------------------------------------------------------- course layout

def course_layout(course: Course) -> Fact:
    """Phase boundaries and key course points in metres, so the model never derives them."""
    e = course.entry
    d = float(e["distance"])
    p1, p2, p3 = d / 6, 2 * d / 3, 5 * d / 6
    lines = [
        f"Course: {course.display}",
        f"Early-race 0-{p1:.0f} m; mid-race {p1:.0f}-{p2:.0f} m; late-race starts at {p2:.0f} m; "
        f"last spurt phase {p3:.0f}-{d:.0f} m (finish).",
        f"Position keeping (sections 1-10) covers 0-{d * 10 / 24:.0f} m; one section = {d / 24:.0f} m.",
    ]
    corners = sorted(e.get("corners", []), key=lambda c: c["start"])
    if corners:
        last = corners[-1]
        lines.append("Corners: " + ", ".join(f"{c['start']:.0f}-{c['start'] + c['length']:.0f} m"
                                             for c in corners)
                     + f" (final corner {last['start']:.0f}-{last['start'] + last['length']:.0f} m).")
    final = [s for s in e.get("straights", []) if s["end"] >= d]
    if final:
        lines.append(f"Final straight: {final[0]['start']:.0f}-{d:.0f} m "
                     f"({d - final[0]['start']:.0f} m long).")
    return Fact("Course layout (metres from the start)", lines,
                {"p1": p1, "p2": p2, "p3": p3, "distance": d})
