# Eval results

Latest full run of `racemech eval` (2026-11-23 19:13, commit `08ce101`).
Rewritten by every full run; per-question answers stay in the gitignored `reports/`.

| Model | Passed | Invented numbers | Median s |
|---|---|---|---|
| qwen3.5:9b-q4_K_M | 137/141 | 2 | 4.4 |

## qwen3.5:9b-q4_K_M

| Category | Passed |
|---|---|
| casual | 16/16 |
| characters | 4/4 |
| coverage | 55/58 |
| decline | 6/6 |
| general | 13/14 |
| mechanics | 9/9 |
| skill | 17/17 |
| stamina | 8/8 |
| stats | 8/8 |
| strategy | 1/1 |

Failed:
- `general-stamina-hp`: missing one of ['0.8']
- `cov-strategy-coef`: missing one of ['0.931']
- `cov-straight-random`: missing one of ['equal', 'same chance', 'regardless']
- `cov-stamina-keep`: missing one of ['1.035', '1.04']
