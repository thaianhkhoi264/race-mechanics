# Eval results

Latest full run of `racemech eval` (2026-11-23 22:03, commit `b6f6ccf`).
Rewritten by every full run; per-question answers stay in the gitignored `reports/`.

| Model | Passed | Invented numbers | Median s |
|---|---|---|---|
| qwen3.5:9b-q4_K_M | 140/141 | 0 | 3.8 |

## qwen3.5:9b-q4_K_M

| Category | Passed |
|---|---|
| casual | 16/16 |
| characters | 4/4 |
| coverage | 58/58 |
| decline | 6/6 |
| general | 13/14 |
| mechanics | 9/9 |
| skill | 17/17 |
| stamina | 8/8 |
| stats | 8/8 |
| strategy | 1/1 |

Failed:
- `general-stamina-hp`: missing one of ['0.8']
