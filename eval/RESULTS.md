# Eval results

Latest full run of `racemech eval` (2026-11-23 18:47, commit `9fd8644`).
Rewritten by every full run; per-question answers stay in the gitignored `reports/`.

| Model | Passed | Invented numbers | Median s |
|---|---|---|---|
| qwen3.5:9b-q4_K_M | 136/141 | 3 | 4.5 |

## qwen3.5:9b-q4_K_M

| Category | Passed |
|---|---|
| casual | 16/16 |
| characters | 3/4 |
| coverage | 55/58 |
| decline | 6/6 |
| general | 13/14 |
| mechanics | 9/9 |
| skill | 17/17 |
| stamina | 8/8 |
| stats | 8/8 |
| strategy | 1/1 |

Failed:
- `general-pace-down`: missing one of ['0.6', '60%', 'hp use', 'less hp', 'saves hp']
- `cov-straight-random`: missing one of ['equal', 'same chance', 'regardless']
- `cov-spot-struggle`: missing one of ['guts']
- `cov-stamina-keep`: missing one of ['1.035', '1.04']
- `char-ny-dia-cm24`: missing one of ['late surger']
