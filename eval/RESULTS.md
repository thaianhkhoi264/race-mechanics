# Eval results

Latest full run of `racemech eval` (2026-11-23 20:58, commit `95f7a11`).
Rewritten by every full run; per-question answers stay in the gitignored `reports/`.

| Model | Passed | Invented numbers | Median s |
|---|---|---|---|
| qwen3.5:9b-q4_K_M | 137/141 | 3 | 3.8 |

## qwen3.5:9b-q4_K_M

| Category | Passed |
|---|---|
| casual | 15/16 |
| characters | 4/4 |
| coverage | 57/58 |
| decline | 6/6 |
| general | 14/14 |
| mechanics | 9/9 |
| skill | 15/17 |
| stamina | 8/8 |
| stats | 8/8 |
| strategy | 1/1 |

Failed:
- `cm21-inherited-moving-past`: missing one of ['0.2']
- `casual-inherited-typo`: missing number 89±2
- `cov-stamina-keep`: missing one of ['1.035', '1.04']
- `sim-budding-verdict-cm22`: missing one of ['did not fire', "didn't fire", 'not fire', 'not firing', 'without']
