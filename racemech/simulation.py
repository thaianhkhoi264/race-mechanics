"""
Facts from community CM simulation snapshots: how often a skill fires on real players' builds,
where, and how often its owner wins when it does. Snapshots are copied here by ``racemech sync``
and read with the ``sim_module`` of the ``bot_repo`` codebase.

Numbers are from simulated races of real teams, and they show correlation, not cause: runners
already in a good position fire more skills and win more.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# The snapshots' style labels -> ours
STYLES = {"Nige": "front", "Senko": "pace", "Sashi": "late", "Oikomi": "end", "Oonige": "runaway"}
STYLE_NAME = {"front": "Front Runner", "pace": "Pace Chaser", "late": "Late Surger", "end": "End Closer",
              "runaway": "Runaway"}
MIN_SAMPLE = 2000          # runner-races owning the skill, per style, before we trust a rate


@dataclass
class StyleStats:
    style: str
    owned: int
    activated: int
    win_active: float | None
    win_inactive: float | None
    win_without: float | None
    earliest_m: float | None = None
    share_earliest: float | None = None
    median_m: float | None = None
    win_early: float | None = None
    win_later: float | None = None

    @property
    def rate(self) -> float:
        return self.activated / self.owned if self.owned else 0.0


@dataclass
class SkillStats:
    base_id: str
    snapshot_id: str
    styles: dict[str, StyleStats] = field(default_factory=dict)
    history: dict[str, list[float]] = field(default_factory=dict)    # style -> activation rate per day
    distance: float = 0.0


def _ratio(a: float, b: float) -> float | None:
    return a / b if b else None


def base_id(skill_id: str, overview: dict) -> str | None:
    """The snapshots group a skill with its inherited copy under one base id."""
    for base, ids in (overview.get("variants") or {}).items():
        if int(skill_id) in ids:
            return base
    return skill_id if any(str(r[0]) == skill_id for r in overview.get("rows", [])) else None


def _timing(stat: StyleStats, rows: list[list], distance: float) -> None:
    """rows: [bucket (% of race), procs, firstEntries, firstIndividualWins, firstTeamWins]."""
    total = sum(r[1] for r in rows)
    if not total:
        return
    first = min(r[0] for r in rows)
    early = [r for r in rows if r[0] <= first + 1]          # the earliest point and the next 1%
    stat.earliest_m = first / 100 * distance
    stat.share_earliest = sum(r[1] for r in early) / total
    running = 0
    for r in sorted(rows):
        running += r[1]
        if running >= total / 2:
            stat.median_m = r[0] / 100 * distance
            break
    late = [r for r in rows if r[0] > first + 1]
    stat.win_early = _ratio(sum(r[3] for r in early), sum(r[2] for r in early))
    stat.win_later = _ratio(sum(r[3] for r in late), sum(r[2] for r in late))


def skill_stats(skill_id: str, snapshots: list[dict]) -> SkillStats | None:
    """Stats from the newest snapshot (with stability across all of them), or None."""
    if not snapshots:
        return None
    latest = snapshots[-1]
    overview = latest["overview"]
    base = base_id(skill_id, overview)
    if base is None:
        return None
    population = overview.get("populationByStyle") or {}
    distance = float(overview.get("courseDistance") or 0)
    out = SkillStats(base, latest["snapshot_id"], distance=distance)
    details = (latest.get("details") or {}).get(base) or {}
    for row in overview.get("rows", []):
        if str(row[0]) != base or row[1] not in STYLES:
            continue
        _, label, _players, owned, activated, _procs, _rep, wins_act, wins_inact, _ta, _ti = row
        pop_entries, pop_wins = (population.get(label) or [0, 0])[:2]
        stat = StyleStats(STYLES[label], owned, activated,
                          _ratio(wins_act, activated), _ratio(wins_inact, owned - activated),
                          _ratio(pop_wins - wins_act - wins_inact, pop_entries - owned))
        if details.get("styles", {}).get(label) and distance:
            _timing(stat, details["styles"][label], distance)
        out.styles[stat.style] = stat
    for snap in snapshots:
        sbase = base_id(skill_id, snap["overview"])
        for row in snap["overview"].get("rows", []):
            if str(row[0]) == sbase and row[1] in STYLES and row[3]:
                out.history.setdefault(STYLES[row[1]], []).append(row[4] / row[3])
    return out if out.styles else None


def phase_of(m: float, distance: float) -> str:
    """Race phase at a position, so the model never works it out itself."""
    if m < distance / 6:
        return "early-race"
    if m < distance * 2 / 3:
        return "mid-race"
    if m < distance * 5 / 6:
        return "late-race"
    return "last spurt phase"


def _ratio_text(st: StyleStats) -> str:
    if st.win_active and st.win_inactive:
        r = st.win_active / st.win_inactive
        if r >= 1.2:
            return f" Owners won {r:.1f}x as often when it fired as when it did not."
        if r <= 1 / 1.2:
            return f" Owners won {1 / r:.1f}x as often when it did NOT fire as when it fired."
    return ""


def _span_phase(lo: float, hi: float, distance: float) -> str:
    a, b = phase_of(lo, distance), phase_of(hi - 0.01, distance)
    if a == b:
        return a
    if b == "late-race":
        return "around the start of late-race"
    return f"{a} into {b}"


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def describe(stats: SkillStats, meta: dict, styles: list[str] | None = None) -> list[str]:
    """Plain lines for the model; ``styles`` limits to the asker's style(s)."""
    m = meta.get("meta") or {}
    lines = [f"Source: simulations for this CM, snapshot {stats.snapshot_id}: "
             f"{m.get('cumulativeSimulations', 0):,} simulated races of {m.get('evaluatedTeams', 0):,} real "
             f"players' teams captured through {m.get('capturedThrough', '?')}. These show correlation, not "
             "cause: runners already in a good position fire more skills and win more."]
    wanted = [s for s in (styles or STYLE_NAME) if s in stats.styles]
    for s in wanted:
        st = stats.styles[s]
        name = STYLE_NAME[s]
        small = " (small sample, treat with care)" if st.owned < MIN_SAMPLE else ""
        lines.append(f"{name}: FIRE RATE {_pct(st.rate)}: of {st.owned:,} simulated races where a {name} "
                     f"had this skill, it fired in {_pct(st.rate)} and did not fire in "
                     f"{_pct(1 - st.rate)}{small}.")
        lines.append(f"{name} WIN RATE: {_pct(st.win_active)} when it fired, {_pct(st.win_inactive)} when "
                     f"they had it but it did not fire, {_pct(st.win_without)} for {name}s without it."
                     + _ratio_text(st))
        if st.earliest_m is not None:
            d = stats.distance
            lo, hi = st.earliest_m, st.earliest_m + d / 100 * 2       # earliest bucket + the next 1%
            lines.append(f"{name} timing: {_pct(st.share_earliest)} of activations happen in its earliest "
                         f"stretch ({lo:,.0f}-{hi:,.0f} m, {_span_phase(lo, hi, d)}); median position "
                         f"{st.median_m:,.0f} m ({phase_of(st.median_m, d)}). Won {_pct(st.win_early)} when "
                         f"it fired in that earliest stretch vs {_pct(st.win_later)} when it fired later.")
        hist = stats.history.get(s, [])
        if len(hist) > 1:
            lines.append(f"{name} stability: fire rate {_pct(min(hist))} to {_pct(max(hist))} across "
                         f"{len(hist)} daily snapshots.")
    if not wanted:
        lines.append("No runner of the asked running style owned this skill in the simulations.")
    return lines
