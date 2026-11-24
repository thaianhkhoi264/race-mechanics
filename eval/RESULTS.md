# Eval results

Latest full run of `racemech eval` (2026-11-23 22:46, commit `ee0ee0a`).
Rewritten by every full run; per-question answers stay in the gitignored `reports/`.

| Model | Passed | Invented numbers | Median s |
|---|---|---|---|
| qwen3.5:9b-q4_K_M | 139/141 | 1 | 3.6 |

## qwen3.5:9b-q4_K_M

| Category | Passed |
|---|---|
| casual | 16/16 |
| characters | 4/4 |
| coverage | 56/58 |
| decline | 6/6 |
| general | 14/14 |
| mechanics | 9/9 |
| skill | 17/17 |
| stamina | 8/8 |
| stats | 8/8 |
| strategy | 1/1 |

Failed:
- `cov-straight-random`: missing one of ['equal', 'same chance', 'regardless']
- `cov-stamina-keep`: missing one of ['1.035', '1.04']
