"""
Why a skill can't activate on a course (or for a running style), read from its condition string.

A condition is OR-groups separated by "@", each an AND of "field<op>value" tokens; a skill has up
to two alternatives. A skill is blocked only if every group of every alternative is blocked.
"""
from __future__ import annotations

import re

from racemech.botlib import Course

STYLES = {1: "Front Runner", 2: "Pace Chaser", 3: "Late Surger", 4: "End Closer"}
STYLE_IDS = {"front": 1, "pace": 2, "late": 3, "end": 4}
_DISTANCE = {1: "Sprint", 2: "Mile", 3: "Medium", 4: "Long"}
_SURFACE = {1: "turf", 2: "dirt"}
_ROTATION = {1: "right-handed (clockwise)", 2: "left-handed (counter-clockwise)"}
_GROUND = {"Firm": 1, "Good": 2, "Soft": 3, "Heavy": 4}
_GROUND_NAME = {1: "Firm", 2: "Good", 3: "Soft", 4: "Heavy"}
_SEASON = {"Spring": (1, 5), "Summer": (2,), "Fall": (3,), "Autumn": (3,), "Winter": (4,)}
_SEASON_NAME = {1: "spring", 2: "summer", 3: "fall", 4: "winter", 5: "spring (cherry blossom)"}
_WEATHER = {"Sunny": 1, "Cloudy": 2, "Rainy": 3, "Rain": 3, "Snow": 4, "Snowy": 4}
_WEATHER_NAME = {1: "sunny", 2: "cloudy", 3: "rainy", 4: "snowy"}
_TOKEN = re.compile(r"([a-z_0-9]+)(==|!=)(-?\d+)")


def _course_values(course: Course, track_names: dict[int, str]) -> dict[str, tuple[set[int], str]]:
    """field -> (values the course has, how to describe the course for that field)."""
    e = course.entry
    out = {
        "track_id": ({e.get("raceTrackId")}, track_names.get(e.get("raceTrackId"), "this racecourse")),
        "rotation": ({e.get("turn")}, _ROTATION.get(e.get("turn"), "this direction")),
        "ground_type": ({e.get("surface")}, _SURFACE.get(e.get("surface"), "this surface")),
        "distance_type": ({e.get("distanceType")}, _DISTANCE.get(e.get("distanceType"), "this distance")),
        "is_basis_distance": ({1 if e.get("distance", 0) % 400 == 0 else 0},
                              f"{e.get('distance')} m ({'' if e.get('distance', 0) % 400 == 0 else 'not '}"
                              "a multiple of 400 m)"),
    }
    cm = course.cm or {}
    if cm.get("ground") in _GROUND:
        out["ground_condition"] = ({_GROUND[cm["ground"]]}, cm["ground"])
    if cm.get("season") in _SEASON:
        out["season"] = (set(_SEASON[cm["season"]]), cm["season"].lower())
    if cm.get("weather") in _WEATHER:
        out["weather"] = ({_WEATHER[cm["weather"]]}, cm["weather"].lower())
    return out


def _needs(field: str, value: int, track_names: dict[int, str]) -> str:
    return {
        "track_id": f"only at {track_names.get(value, f'track {value}')}",
        "rotation": f"only on {_ROTATION.get(value, value)} courses",
        "ground_type": f"only on {_SURFACE.get(value, value)}",
        "distance_type": f"only in {_DISTANCE.get(value, value)} races",
        "is_basis_distance": ("only at distances that are a multiple of 400 m" if value == 1
                              else "only at distances that are not a multiple of 400 m"),
        "ground_condition": f"only on {_GROUND_NAME.get(value, value)} ground",
        "season": f"only in {_SEASON_NAME.get(value, value)}",
        "weather": f"only in {_WEATHER_NAME.get(value, value)} weather",
        "running_style": f"only for {STYLES.get(value, value)}s",
    }[field]


def _group_blockers(group: str, have: dict, track_names: dict[int, str]) -> list[str]:
    reasons = []
    for field, op, raw in _TOKEN.findall(group):
        if field not in have:
            continue
        value, (values, what) = int(raw), have[field]
        if (op == "==" and value not in values) or (op == "!=" and value in values):
            need = _needs(field, value, track_names) if op == "==" else f"not with {what}"
            reasons.append(f"{need}; this course is {what}" if field != "running_style" else
                           f"{need}; the question is about a {what}")
    return reasons


def blockers(entry: dict, course: Course, track_names: dict[int, str], style: str | None = None) -> list[str]:
    """Reasons the skill can never activate here (empty if at least one condition group can).
    With ``style`` the running style is checked too."""
    have = _course_values(course, track_names)
    if style in STYLE_IDS:
        have["running_style"] = ({STYLE_IDS[style]}, STYLES[STYLE_IDS[style]])
    all_reasons: list[str] = []
    for alt in entry.get("alternatives", []):
        for group in (alt.get("condition") or "").split("@"):
            reasons = _group_blockers(f"{group}&{alt.get('precondition') or ''}", have, track_names)
            if not reasons:
                return []
            all_reasons += [r for r in reasons if r not in all_reasons]
    return all_reasons
