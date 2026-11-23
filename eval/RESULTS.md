# Eval results

Latest full run of `racemech eval` (2026-11-23 04:40, commit `97cc82b`).
Rewritten by every full run; per-question answers stay in the gitignored `reports/`.

| Model | Passed | Invented numbers | Median s |
|---|---|---|---|
| qwen3.5:9b-q4_K_M | 136/141 | 3 | 4.4 |

## qwen3.5:9b-q4_K_M

| Category | Passed |
|---|---|
| casual | 15/16 |
| characters | 4/4 |
| coverage | 56/58 |
| decline | 6/6 |
| general | 12/14 |
| mechanics | 9/9 |
| skill | 17/17 |
| stamina | 8/8 |
| stats | 8/8 |
| strategy | 1/1 |

Failed:
- `casual-kanata`: missing number 550±0
- `general-pace-down`: missing one of ['0.945']
- `general-stamina-hp`: missing one of ['0.8']
- `cov-block`: missing one of ['2 m', '2m', '2 meters', '2 metres']
- `cov-spot-struggle`: missing one of ['guts']
