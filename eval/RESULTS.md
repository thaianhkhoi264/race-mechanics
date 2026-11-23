# Eval results

Latest full run of `racemech eval` (2026-11-23 04:25, commit `c950487`).
Rewritten by every full run; per-question answers stay in the gitignored `reports/`.

| Model | Passed | Invented numbers | Median s |
|---|---|---|---|
| qwen3.5:9b-q4_K_M | 135/141 | 4 | 3.8 |

## qwen3.5:9b-q4_K_M

| Category | Passed |
|---|---|
| casual | 16/16 |
| characters | 4/4 |
| coverage | 56/58 |
| decline | 6/6 |
| general | 11/14 |
| mechanics | 9/9 |
| skill | 17/17 |
| stamina | 8/8 |
| stats | 7/8 |
| strategy | 1/1 |

Failed:
- `general-pace-down`: missing one of ['0.945']; missing one of ['0.6', '60%', 'hp use', 'less hp', 'saves hp']
- `general-downhill`: missing one of ['60%', '0.4', '40%']
- `general-guts-front`: missing one of ['spot struggle', 'lead competition']
- `stat-wit-cm21`: missing one of ['not a concern', 'not a major concern', 'not an issue', 'not a problem', "doesn't matter", 'does not matter', "isn't a concern", 'relatively minor', 'sprint']
- `cov-straight-random`: missing one of ['equal', 'same chance', 'regardless']
- `cov-stamina-keep`: missing one of ['1.035', '1.04']
