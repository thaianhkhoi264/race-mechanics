"""
Stat formulas from the race mechanics notes (KuromiAK's document), as pure functions.

Percentages are returned as percent (e.g. 85.0 for 85%). Wit here is the runner's Wit with
strategy aptitude applied, except ``skill_activation_pct`` which uses base Wit.
"""
from __future__ import annotations

import math

SLOPE_SCALE = 10000.0      # course_data.json slope 10000 = 1% grade
DOWNHILL_EXIT = 0.2        # per second


def skill_activation_pct(base_wit: float) -> float:
    """Pre-race Wit check for skills: max(100 - 9000 / Wit, 20)%."""
    return max(100.0 - 9000.0 / base_wit, 20.0)


def rushed_pct(wit: float) -> float:
    """Chance to get rushed (kakari): (6.5 / log10(0.1 x Wit + 1))^2 %, rounded up."""
    return float(math.ceil((6.5 / math.log10(0.1 * wit + 1)) ** 2))


def pace_up_check_pct(wit: float) -> float:
    """Position keeping check (non-front styles' pace-up): 15 x log10(Wit x 0.1)%, every 2 s."""
    return 15.0 * math.log10(wit * 0.1)


def front_check_pct(wit: float) -> float:
    """Front Runner speed-up/overtake check: 20 x log10(Wit x 0.1)%, every 2 s."""
    return 20.0 * math.log10(wit * 0.1)


def section_random_pct(wit: float) -> tuple[float, float]:
    """Random target-speed range per section, as % of base speed: (min, max)."""
    hi = wit / 5500.0 * math.log10(wit * 0.1)
    return hi - 0.65, hi


def spurt_accept_pct(wit: float) -> float:
    """Chance each faster last-spurt candidate is accepted when HP is short."""
    return min(15.0 + 0.05 * wit, 100.0)


def downhill_mode_share(wit: float) -> float:
    """Steady-state fraction of downhill time spent in downhill accel mode (0-1)."""
    enter = wit * 0.0004
    return enter / (enter + DOWNHILL_EXIT)


def base_speed(distance: float) -> float:
    return 20.0 - (distance - 2000.0) / 1000.0


def uphill_loss(raw_slope: float, power: float) -> float:
    """Target-speed loss on an uphill in m/s: slope% x 200 / Power."""
    return raw_slope / SLOPE_SCALE * 200.0 / power


def downhill_boost(raw_slope: float) -> float:
    """Target-speed bonus in downhill accel mode, m/s: 0.3 + slope%/10."""
    return 0.3 + abs(raw_slope) / SLOPE_SCALE / 10.0


def downhill_gain_m(slopes: list[dict], wit: float, speed: float) -> float:
    """Expected metres gained over the given downhills: time on them x share in the mode x boost."""
    share = downhill_mode_share(wit)
    return sum(s["length"] / speed * share * downhill_boost(s["slope"]) for s in slopes)


def skill_duration_s(base_duration: float, distance: float) -> float:
    """Duration = baseDuration/10000 x CourseDistance/1000 (longer on longer courses)."""
    return base_duration / 10000.0 * distance / 1000.0


def speed_carryover(fire_m: float, base_duration: float, distance: float,
                    speed_bonus: float) -> dict:
    """
    Where a speed skill fired at ``fire_m`` ends, and how much of it is still running when
    late-race (the last spurt) starts at 2/3 of the distance. Same model as the
    bot_repo calculators: the runner covers ground at base speed + the skill's own bonus while it lasts.
    """
    dur = skill_duration_s(base_duration, distance)
    speed = base_speed(distance) + speed_bonus
    end = fire_m + speed * dur
    late = distance * 2 / 3
    over_m = max(0.0, end - late) if fire_m < late else 0.0
    return {"duration_s": dur, "speed": speed, "covers_m": speed * dur, "end_m": end, "late_m": late,
            "carry_m": min(over_m, speed * dur), "carry_s": min(over_m, speed * dur) / speed,
            "short_m": max(0.0, late - end)}
