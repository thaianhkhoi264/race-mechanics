# Skill system

## Skill IDs and rarity
Skill IDs: 2XXXXX and 3XXXXX are regular skills anyone can learn (white = rarity 1, gold =
rarity 2). 1XXXXX (6 digits) are character unique skills (rarity 5; evolved uniques rarity 4;
old 5-digit base uniques rarity 3). 9XXXXX are inherited copies of a unique skill, with about half
its effect; the source unique is "1" + the rest of the ID (900591 -> 100591). 9-digit IDs are
special or event skills.

## Gold and white skills
A gold skill and its white version share every digit but the last (the same skill group). The
gold is usually the white's ID ending in 1 instead of 2 (Early Lead 200532 -> Taking the Lead
200531, Slick Surge 200602 -> On Your Left! 200601) but not always (Groundwork 201601 is white and
Solid Preparation 201602 is gold). Some skills come in three tiers with symbols in the name: ◎ is
the strongest, ○ the normal version, × a weaker or negative version (Right-Handed ◎ +60 Speed,
○ +40, × -40). Prefer the strongest positive tier and the gold version when one exists.

## Effect types
Effect types: 1 Speed, 2 Stamina, 3 Power, 4 Guts, 5 Wit (flat stat bonus, "green" skills);
9 HP recovery (fraction of max HP; negative on opponents = HP debuff); 21 current speed (instant);
22 current speed with natural deceleration; 27 target speed (the usual "velocity" skill); 28 lane
movement speed; 31 acceleration; 8 field of view (usually a debuff); 13/29 rushed duration and
chance. Values in skill data are divided by 10000 (modifier 3500 = +0.35 m/s target speed).

## Condition and precondition
A skill has a condition (when it fires) and sometimes a precondition (something that must happen
first to arm it). Conditions are field comparisons joined by & (and); @ separates alternative
clauses (or). Only the condition decides whether activation is random or deterministic; the
precondition is an eligibility gate. Deterministic conditions fire at the first moment they are
true; conditions with random fields (phase_random, all_corner_random, straight_random,
is_overtake, blocked_*, near_count, ...) fire at an unpredictable point inside their window.

## Common condition fields
phase: 0 early, 1 mid, 2 late, 3 last spurt. corner: 0 = on a straight, 1-4 = the track's corner
number (not the order you run them). is_finalcorner, is_last_straight: the final corner / final
straight. order: placing (1 = first). order_rate: placing as a percentage of the field, converted
to a placing by rounding to nearest. running_style: 1 Front Runner, 2 Pace Chaser, 3 Late Surger,
4 End Closer. distance_type: 1 Sprint, 2 Mile, 3 Medium, 4 Long. change_order_onetime < 0 means
you just overtook someone; > 0 means you were just overtaken. temptation_count==0 means not rushed.
blocked_side_continuetime / blocked_front_continuetime are seconds blocked. activate_count_start /
activate_count_middle count skills already activated in early / mid race. is_overtake==1 means
you have an overtake target. order_rate_out70_continue==1 means you stayed outside the top 70%
(the back 30%) for the whole race so far, ignoring the first 5 seconds.

## Champions Meeting field size and placings
Champions Meeting races have 9 runners, so order_rate converts to placings out of 9:
order_rate<=50 -> top 5 (rounding 4.5 up), order_rate>=40 -> 4th or worse, order_rate<=40 -> top 4,
order_rate>=50 -> 5th or worse, order_rate>50 -> 6th or worse, order_rate<=75 -> top 7.
League of Heroes races have 12 runners, so the same percentages give different placings.
Typical placings per style in a 9-runner CM: Front Runner 1st-2nd, Pace Chaser 1st-4th, Late
Surger 5th-8th, End Closer 6th-9th.

## Timing relative to late-race
Most acceleration and speed skills are judged by where they fire relative to the start of
late-race (2/3 of the distance). An acceleration skill is ideal within about 10 m of late-race
start; 10-50 m off is slightly worse; further off is much worse. Firing early only helps Front
Runners at the race start (to take the lead). A velocity skill that fires shortly before
late-race and is still active when late-race starts "carries over" its speed into the spurt
(speed carryover).

## Acceleration ratings
The bot rates acceleration skills by size and timing. Regular and unique skills: 0.35+ very high,
0.25+ high, 0.15+ moderate, below that low; the rating (Weak / Decent / Good / Great accel) drops
one or two steps when the skill fires away from late-race start or at a random point. Inherited
skills use a lower scale (0.18+ high, 0.08+ moderate).

## Inherited skills
Inherited (9XXXXX) skills keep the unique skill's activation condition but have about half the
effect and a shorter duration (for example Superior Heal recovers 7.5% HP as a unique, 3.5% when
inherited). They are learned by passing the unique through inheritance (sparks).
