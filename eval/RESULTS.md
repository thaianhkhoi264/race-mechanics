# Eval results

Latest full run of `racemech eval` (2026-11-23 20:05, commit `834c766`).
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
| general | 14/14 |
| mechanics | 9/9 |
| skill | 17/17 |
| stamina | 8/8 |
| stats | 7/8 |
| strategy | 1/1 |

Failed:
- `stat-wit-cm21`: missing one of ['length', 'lengths']
- `cov-pace-up-ex`: missing one of ['2.0', '2x', 'double']
- `cov-spot-struggle`: missing one of ['guts']
- `cov-stamina-keep`: missing one of ['1.035', '1.04']
