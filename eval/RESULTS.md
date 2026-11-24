# Eval results

Latest full run of `racemech eval` (2026-11-24 02:19, commit `4c48590`).
Rewritten by every full run; per-question answers stay in the gitignored `reports/`.

| Model | Passed | Invented numbers | Median s |
|---|---|---|---|
| qwen3.5:9b-q4_K_M | 139/141 | 1 | 3.7 |

## qwen3.5:9b-q4_K_M

| Category | Passed |
|---|---|
| casual | 16/16 |
| characters | 4/4 |
| coverage | 58/58 |
| decline | 6/6 |
| general | 13/14 |
| mechanics | 9/9 |
| skill | 16/17 |
| stamina | 8/8 |
| stats | 8/8 |
| strategy | 1/1 |

Failed:
- `general-stamina-hp`: missing one of ['0.8']
- `sim-budding-verdict-cm22`: missing one of ['did not fire', "didn't fire", 'not fire', 'not firing', 'without']
