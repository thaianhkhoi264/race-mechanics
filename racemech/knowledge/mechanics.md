# Race mechanics

The numbers and formulas behind a race, as the assistant uses them. The formulas come from
community reverse-engineering, mainly KuromiAK's "Uma Musume Race Mechanics"
(https://docs.google.com/document/d/15VzW9W2tXBBTibBRbZ8IVpW6HaMX8H0RP03kq6Az7Xg/), which builds
on work by @umamusu_reveng, @kak_eng and @hoffe_33. The text and organisation here are ours.
"Inferred" marks rules taken from the game's parameter files, which are less certain; "uncertain"
marks a formula whose exact shape isn't known.

## Course geometry: 24 sections, four phases, late-race start
Take a course of length d. It is divided into 24 sections of equal length (d/24 each), and the
sections are grouped into four phases:

| Phase | Sections | Begins at |
|---|---|---|
| early-race (phase 0) | 1-4 | the gate |
| mid-race (phase 1) | 5-16 | d/6 |
| late-race (phase 2) | 17-20 | 2d/3 |
| last-spurt phase (phase 3) | 21-24 | 5d/6 |

The late-race start, 2d/3 (written p2), matters most: acceleration timing and speed carryover are
both judged against it. Two names are easy to mix up. The last-spurt *phase* only means sections
21-24, while the last-spurt *state*, the runner's final push (see Speed), already begins at p2.
Internally the race advances in steps of about 0.0666 s, i.e. 15 updates per second.

## Distances on the track: lengths, lanes, course width
Gaps between runners are counted in lengths (bashin), and 1 length = 2.5 m, the same unit the
simulators use. Sideways position is counted outward from the inner rail. One course width is
11.25 m; a horse lane is 1/18 of that, about 0.625 m. A runner who swings wide through a corner,
or keeps changing lanes, covers more ground than the course distance.

## How trained stats become race stats
A stat passes through three steps before the race reads it.
1. Range and soft cap: stats go from 1 to 2000 (2500 since the 5th anniversary), and each raw
   point past 1200 is only worth half a point.
2. Base stat = (raw stat + bonuses) x mood multiplier. Mood: Perfect 1.04, Good 1.02, Normal 1.0,
   Bad 0.98, Terrible 0.96. Skill activation chances read this base Wit.
3. Adjusted stat: track and style then modify the base value.
   - Heavy ground takes 50 off Speed, on turf and dirt alike.
   - Power on turf: -50 when Good, Soft or Heavy.
   - Power on dirt: -100 when Firm, -50 when Good, -100 when Soft or Heavy.
   - Running-style (strategy) aptitude multiplies Wit: S 1.1, A 1.0, B 0.85, C 0.75, D 0.6,
     E 0.4, F 0.2, G 0.1.
A few courses also hand out up to +20% Speed to runners whose listed threshold stats are high.

## Speed in a race: what it is used for
Speed starts to count only at the late-race start. It adds sqrt(500 x Speed) x distance
aptitude x 0.002 m/s to the late-race target speed and to the max spurt speed (roughly +1.73 m/s
at 1500 Speed and +1.79 at 1600, grade A). Early and mid-race target speed ignore it. A faster
spurt burns HP faster, so extra Speed raises the Stamina a full spurt needs. Past 2000 it unlocks
the zenkai spurt.

## Stamina in a race: what it is used for
Stamina is turned into HP once, at the gate (see HP). It decides whether the runner can
afford the full last spurt; it never changes speed or acceleration by itself. Past 1200 (skill
bonuses included) it unlocks the stamina limit break, but only in races of at least 2101 m.
Healing skills restore a share of max HP, so each one is worth more the more Stamina she has and the longer
the race is.

## Power in a race: what it is used for
Power is acceleration: the higher it is, the sooner she reaches her target speed after the
gate, after being slowed and when the spurt begins. It also shrinks the uphill slowdown, speeds
up lane changes (lane-change speed about 0.02 x (0.3 + 0.001 x Power), uncertain), stores conserve
power past 1200, and scales the zenkai spurt's acceleration.

## Guts in a race: what it is used for
Guts cuts late-race HP drain through the factor 1 + 200 / sqrt(600 x Guts) (1.333 at 600
Guts), adds (450 x Guts)^0.597 x 0.0001 m/s to max spurt speed (about +0.17 m/s at 600), lifts
minimum speed, sets the size of the Dueling (showdown) bonus on the final straight, and takes part
in the compete-before-spurt check. For Front Runners it also powers the spot struggle, their
early fight for the lead: both the speed gained and how long it lasts grow with Guts.

## Wit in a race: what it is used for
Wit has the widest reach: the skill activation check, the Rushed chance, the
position-keeping checks (pace-up, front-runner speed-up and overtake), how far the random section
speed can fall, accepting faster spurt candidates when HP is short, entering downhill accel mode,
the stamina keep and compete-before-spurt checks (exact formulas uncertain), and the Wit limit
break past 1200. Late starts are the one thing it doesn't touch.
## Base speed of a course
Every speed in a race is built on the course's base speed, which depends on nothing but the
distance d: base_speed = 20.0 - (d - 2000) / 1000 m/s. So 1200 m gives 20.8 m/s, 1600 m 20.4,
2000 m 20.0, 2400 m 19.6 and 2500 m 19.5.

## Target speed: what the runner is aiming for
At every moment a runner has a target speed and accelerates or slows toward it. The game never
lets it go above 30 m/s or under minimum speed. It is put together as:
target = (base target speed, or spurt speed once spurting) x position-keeping multiplier
+ skill target-speed bonuses + early-race force-in bonus + lane-move bonus + slope terms.
Skill bonuses are plain m/s amounts that are summed.

The base target speed depends on the phase:
- Early and mid-race: base_speed x the style's phase coefficient. The Speed stat plays no part.
- Late-race and last spurt: base_speed x the style's late coefficient
  + sqrt(500 x Speed) x distance aptitude x 0.002.

| Style | early | mid | late |
|---|---|---|---|
| Front Runner | 1.0 | 0.98 | 0.962 |
| Pace Chaser | 0.978 | 0.991 | 0.975 |
| Late Surger | 0.938 | 0.998 | 0.994 |
| End Closer | 0.931 | 1.0 | 1.0 |
| Runaway | 1.063 | 0.962 | 0.95 |

Distance aptitude in the Speed term: S 1.05, A 1.0, B 0.9, C 0.8, D 0.6, E 0.4, F 0.2, G 0.1.

## Section-by-section randomness
Outside the last spurt, each section adds a random share of base_speed to the target speed. The
range comes from Wit: top = Wit / 5500 x log10(Wit x 0.1) %, bottom = top - 0.65 %. With 400 Wit
that is +0.117% to -0.533%; with 800 Wit, +0.277% to -0.373%. More Wit mainly lifts the bottom.

## The last spurt
- When it is planned: at the start of mid-race the game works out the spurt in advance.
- Top speed it can reach: max spurt speed = (late-race base target speed + 0.01 x base_speed)
  x 1.05 + sqrt(500 x Speed) x distance aptitude x 0.002 + (450 x Guts)^0.597 x 0.0001.
- At the late-race start, a runner whose HP covers the rest of the race at that speed starts
  spurting at it straight away.
- Short on HP: the game tries slower speeds, 0.1 m/s lower each time, down toward the late-race
  base target speed. The options are ranked by finish time and each one is taken with a chance of
  15 + 0.05 x Wit %; if every roll fails she gets the slowest one.
- The HP sum stops 60 m short of the goal and leaves out time spent accelerating.
- A recovery skill that fires after the late-race start makes the game redo the plan; a debuff
  doesn't.
- "Minimum Stamina for a full spurt" is the Stamina at which she can hold max spurt speed from the
  late-race start to the finish.

## Minimum speed
Once the start dash is over, speed never falls below minimum speed =
0.85 x base_speed + sqrt(200 x Guts) x 0.001 m/s. This is also what she drops to at 0 HP.

## Acceleration and deceleration
Acceleration = base acceleration x sqrt(500 x Power) x style phase coefficient x ground aptitude
x distance aptitude, plus any skill acceleration (summed). Base acceleration is 0.0006 m/s^2 on
the flat and 0.0004 going uphill.

| Style | early | mid | from late-race |
|---|---|---|---|
| Front Runner | 1.0 | 1.0 | 0.996 |
| Pace Chaser | 0.985 | 1.0 | 0.996 |
| Late Surger | 0.975 | 1.0 | 1.0 |
| End Closer | 0.945 | 1.0 | 0.997 |
| Runaway | 1.17 | 0.94 | 0.956 |

Ground aptitude: S 1.05, A 1.0, B 0.9, C 0.8, D 0.7, E 0.5, F 0.3, G 0.1. Distance aptitude
(acceleration only): S to D 1.0, E 0.6, F 0.5, G 0.4.

Start dash: everyone leaves the gate at 3 m/s with an extra 24.0 m/s^2 of acceleration, which
stops once she reaches 0.85 x base_speed.

When target speed is below current speed she slows at a fixed rate: early-race -1.2 m/s^2,
mid-race -0.8, late-race -1.0; -0.5 while in pace-down mode and -1.2 once her HP has run out.

## Kinds of speed skills and how they stack (additive, not multiplicative)
- Effect type 27, the target-speed skills, lift the speed she is aiming for, so acceleration has
  to close the gap before they pay off.
- Speed debuffs come last: they are applied to actual speed after everything else.
- Current-speed skills (type 21) change her actual speed on the spot, applied after the
  acceleration step.
- Type 22 adds actual speed for as long as it lasts, then gives the same amount once more as a
  one-off push to current speed when it ends.
Effects of the same kind are summed: two +0.35 target-speed skills together make +0.70 m/s, two
+0.2 acceleration skills +0.4 m/s^2. Target speed and acceleration are never multiplied together;
acceleration only decides how fast a higher target is reached. Skill level and the Wit limit
break scale a skill's own value (see Skills and Finish).

## Starting HP
HP is fixed at the gate: max HP = 0.8 x style HP coefficient x Stamina + course distance (in m).
Style HP coefficients: Front Runner 0.95, Pace Chaser 0.89, Late Surger 1.0 (the most HP per
Stamina point), End Closer 0.995, Runaway 0.86. Because the course distance is part of max HP, a
percentage of max HP stands for more Stamina points the longer the race.

## How fast HP drains
Per second: 20 x (current speed - base_speed + 12)^2 / 144 x state multiplier x ground multiplier.
Running faster therefore costs more, and the cost grows with the square of the speed.
- State multipliers, combined by multiplying: Rushed 1.6, pace-down mode 0.6, downhill accel mode
  0.4.
- Ground: 1.0 on Firm or Good. Turf: 1.02 on Soft or Heavy. Dirt: 1.01 on Soft, 1.02 on Heavy.
- From the late-race start the drain is also multiplied by the Guts factor
  1 + 200 / sqrt(600 x Guts): 1.577 at 200 Guts, 1.408 at 400, 1.333 at 600.

## Recovery and HP debuffs
A recovery skill gives back a fixed share of max HP at once; HP can't go over the maximum, so any
excess is lost. An HP debuff takes a share of max HP from opponents. Debuffs never touch the
caster's own teammates.

## Running out of HP
At 0 HP her target speed falls to minimum speed (0.85 x base_speed + sqrt(200 x Guts) x 0.001),
she slows down at -1.2 m/s^2, and her target lane no longer changes.

## Stamina keep (inferred)
A runner wants to hold 1.035-1.04x the HP she needs to finish. Every 2 s, if she has less than
that, a Wit-based roll can put her into stamina-keep mode, where she sits out the
compete-before-spurt bursts. Using a recovery skill clears the mode.

## Stamina limit break (inferred, uncertain)
With Stamina plus skill bonuses past 1200, she gets extra target speed from the moment she
reaches max spurt speed until the finish. The bonus grows with the Stamina above 1200, times
0.0085, a distance factor and a random factor; the exact shape isn't known. Distance factor by
course length: under 2101 m 0 (so no effect), under 2201 m 0.5, under 2401 m 1.0, under 2601 m
1.5, 2601 m and longer 1.8.

## Uphills
On a climb her target speed is cut by slope% x 200 / Power m/s, so Power is what keeps a runner
from losing speed on hills; base acceleration also drops to 0.0004 m/s^2 while climbing.

## Downhill accel mode
What it gives: target speed +0.3 + slope%/10 m/s and 60% less HP drain (HP use x0.4), for as
long as it lasts. How a runner gets it: on a downhill the game rolls once per second, and with a
chance of Wit x 0.04 % she enters downhill accel mode (24% per second at 600 Wit, 48% at 1200).
Once in it, each second carries a 20% chance that it ends. On a long downhill the share of time spent in the mode settles
near (Wit x 0.0004) / (Wit x 0.0004 + 0.2): about 55% at 600 Wit and about 71% at 1200. Courses
with long downhills therefore reward Wit twice: extra speed and saved HP.

## Skill activation chance: the Wit check before the race
Before the race, most skills roll against max(100 - 9000 / base Wit, 20) %: 70% at 300 Wit, 85% at
600, 90% at 900, 92.5% at 1200. The roll uses base Wit, so strategy aptitude and Wit-raising skills
don't change it.

## How long a skill lasts: duration and cooldown in seconds
Durations and cooldowns are stretched with the course: real value = listed value x d / 1000. A
skill listed at 4 seconds runs 4.8 s at 1200 m, 6.4 s at 1600 m, 8.8 s at 2200 m and 10 s at 2500 m.

## Skill level
Levelled skills gain strength by multiplier, and the multiplier depends on the effect:

| Level | target speed | acceleration | stat | other (recovery, current speed, lane move) |
|---|---|---|---|---|
| 2 | 1.01 | 1.02 | 1.01 | 1.02 |
| 3 | 1.04 | 1.04 | 1.02 | 1.04 |
| 4 | 1.07 | 1.06 | 1.03 | 1.06 |
| 5 | 1.10 | 1.08 | 1.04 | 1.08 |
| 6 | 1.13 | 1.10 | 1.05 | 1.10 |
| 10 | 1.25 | 1.20 | 1.10 | 1.18 |

## Skills with a random activation point
Conditions ending in _random choose a 10 m stretch before the race; the skill fires when the
runner reaches it and everything else in the condition is true.
- straight_random: first a straight is picked, each straight with the same chance no matter how
  long it is, then a spot on it.
- corner_random: if the race goes through the same corner twice, only the last lap counts.
- all_corner_random: up to 4 trigger spots spread over the corners.
- phase_corner_random: the phase's corners are treated as one stretch, so a long corner is
  likelier to get the spot.

## How skill conditions are evaluated
- Each frame, skills are checked before the phase is updated, one by one in order of skill ID; a
  skill with a lower ID can therefore enable one with a higher ID in the same frame.
- order_rate turns into a placing by rounding: order_rate>50 in a 9-runner Champions Meeting is
  order > round(4.5) = 5, which means 6th or worse.
- remain_distance = course distance - floor(the runner's position).

## What a runner can see, and what counts as near
By default a runner sees 20 m ahead; some skills widen or lengthen that view. Skill conditions
use two distances:
- "near" another runner: within 3 m along the track and within 3 horse lanes sideways;
- right in front of or right behind her (infront_near_lane_time / behind_near_lane_time): within
  2.5 m and 1 horse lane. That timer starts over whenever the placings change.

## Blocking
- Blocked in front: another runner is less than 2 m ahead of her and 0.3-0.75 of a horse lane
  across. Her speed can then be at most 0.988-1.0x that runner's speed.
- Blocked at the side: someone within 1.05 horse lanes to the side and within 2 m.

## Overtake targets and lane moves
A runner ahead counts as an overtake target when she is visible, 1-20 m in front, and the speed
difference would bring them level within 15 s (either because she is slower or because she is
blocked). As long as a runner has targets she is in overtake lane mode, steering to get around
them; skills with an is_overtake condition need at least one target. How quickly she can move
across depends on Power: roughly 0.02 x (0.3 + 0.001 x Power) per step (uncertain), which helps
in getting out from behind a blocker.

## Starting late
At the gate each runner gets a random reaction delay of up to 0.1 s; anything over 0.08 s is a
late start. Wit plays no part in it. With Concentration the delay is x0.4, with Focus x0.9, and Gatekept
makes it x1.5.

## Position keeping: the rules
For the first 10 sections each runner tries to hold her style's place in the field. A check runs
every 2 s and can switch her into one of the modes below; a mode lasts one section at most (three
for a Runaway) and is followed by a 1 s pause before the next one. The reference runner is the
pacemaker, normally the leader; how the game picks it isn't fully known (a 10 m window and a count
of 2 are part of the rule). Runners who aren't Front Runners keep a target gap behind the
pacemaker, which is longer on longer courses (multiplied by 0.0008 x (d - 1000) + 1):

| Style | gap behind the pacemaker |
|---|---|
| Pace Chaser | 3.0 to 5.0 m |
| Late Surger | 6.5 to 7.0 m |
| End Closer | 7.5 to 8.0 m |

## Pace-up mode
Effect: target speed x1.04, held until her gap to the pacemaker is right again.
When: a Pace Chaser, Late Surger or End Closer has fallen further back than her gap allows and
passes a Wit check of 15 x log10(Wit x 0.1) %.

## Pace-down mode (PDM)
Effect: target speed x0.945 in mid-race, i.e. 5.5% slower (x0.915, 8.5% slower, in other
phases), and HP use x0.6, i.e. 40% less HP while in it. She also slows at -0.5 m/s^2 instead of the usual phase rate, drifts toward the
inner lane, and builds up conserved power.
When: a Pace Chaser, Late Surger or End Closer in sections 1-10 is closer to the pacemaker than her
gap allows, while none of her speed or target-speed skills are running.
Ends: when she has dropped back past a random point inside her gap, or as soon as one of her
skills lifts her speed or her target speed.
It isn't a punishment: the HP it saves is real; the risk is ending up too far back.

## Front Runners: speed-up and overtake modes
Front Runners in sections 1-10 have two modes of their own, both gated by a Wit check of
20 x log10(Wit x 0.1) %:
- Speed-up mode. Effect: target speed x1.04. When: she is in front but by less than 4.5 m
  (17.5 m for a Runaway, 12.5 m if she is the only Front Runner).
- Overtake mode. Effect: target speed x1.05. When: she isn't the first of the Front Runners; it
  lasts until she is 10 m clear of the second Front Runner (27.5 m for a Runaway).
This overtake mode is a position-keeping state; it has nothing to do with overtake lane mode,
which is about steering around runners ahead (see Overtake targets and lane moves).

## Pace-up Ex mode
Effect: target speed x2.0, taking priority over the other position-keeping modes.
When: the order of styles is broken. For a Front Runner, someone of a style that should run behind
her is in front; for the others, the pacemaker belongs to a style that should be behind her. It
switches off once nobody of a more backward style is ahead.

## Rushed (JP: kakari)
Effect: she drains HP 1.6x as fast and runs as if she had a more forward style.
Chance: decided by a roll before the race, (6.5 / log10(0.1 x Wit + 1))^2 %, rounded up: about 19%
at 300 Wit, 14% at 600, 12% at 900 and 10% at 1200. Wit is the only stat that lowers it, and it
never gets down to 0%.
Timing: it starts in a random section between 2 and 9. Every 3 s she has a 55% chance to settle;
at the latest it ends after 12 s, though each debuff that prolongs it adds 5 s.

## Spot struggle (lead competition) (inferred)
Effect: a Front Runner or Runaway gains (500 x Guts)^0.6 x 0.0001 m/s of target speed for
(700 x Guts)^0.5 x 0.012 s, so Guts sets both the size and the length of the push. It is
expensive: HP drain 1.4x for a Front Runner (3.6x if also Rushed), 3.5x for a Runaway (7.7x if
also Rushed).
When: from 150 m in, while she is within 3.75 m of the lead runner of her own style and close
beside her; it has to begin before section 6 and is over by section 9 at the latest.

## Secure lead (inferred)
Effect: a 2 s push, paid for in HP.
When: in sections 11-15, a runner whose lead over someone of a more backward style is too thin has
a 20% chance every 2 s.

## Compete before spurt (inferred, uncertain)
Effect: a 2 s burst of speed that costs HP, followed by a 1 s pause.
When: in sections 11-15, every 2 s, for a runner far from the front or with others close around
her. Guts, Wit and the runners around her all feed into it; the formula isn't known.

## Conserve power and its release (inferred)
Effect: extra acceleration when the last spurt begins, sqrt((Power - 1200) x 130) x 0.001 x a
style-and-distance coefficient, for about 3 s.
When: Power plus skill bonuses is above 1200; the power is stored while she runs in normal or
pace-down position keeping.

## Dueling (showdown, compete fight) (inferred)
Effect: each runner in the duel gains (200 x Guts)^0.708 x 0.0001 m/s of target speed and
(160 x Guts)^0.59 x 0.0001 m/s^2 of acceleration, so Guts decides how much a duel is worth.
When: on the final straight, two runners in the top half of the field stay within 3 m of each
other and close beside each other for more than 2 s. A runner under 15% HP can't start one, and it
stops for a runner who falls under 5%.

## Zenkai spurt
A 5th-anniversary addition. A runner with more than 2000 Speed and enough HP keeps gaining speed
after she has reached her spurt speed, and how fast she gains it depends on Power.

## Wit limit break
Also from the 5th anniversary. Above 1200 Wit, speed skills of gold, unique or evolved rarity
are boosted, both kinds: target-speed (effect type 27) and current-speed (type 22). The boost is a multiplier that grows with
the Wit above 1200 (0 at +1, 0.14 at +141, 0.5 at +301, 1.0 at +801, topping out at 1.12), times a
phase coefficient that depends on the running style. White skills and inherited skills don't get
it.

## Finish times and margins
The times shown in the game are the internal times multiplied by 1.18, which is why they look
slower than the simulation. Finishing margins: a nose is 0.2 m, a head 0.4 m, a neck 0.8 m.
