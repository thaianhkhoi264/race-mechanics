# race-mechanics

A local question-answering assistant for Uma Musume (Global) skills and race mechanics,
running entirely on your own PC.

> **Readable, not runnable on its own.** race-mechanics imports calculator modules (skill
> trigger windows, the stamina model, CM course lookup, simulation snapshot reading) from a
> bot_repo codebase checkout at runtime
> (`bot_repo` setting), and answers from game data that `racemech sync` copies from your own
> game client; neither is part of this repo. Without them the code, knowledge files, prompts
> and eval are all here to read, and the tests that need them skip themselves, but
> `racemech ask` / `serve` / `eval` won't start.

**Knowledge files are our own writing.** `racemech/knowledge/` (mechanics, glossary, skills,
strategy) is written in our own words. The mechanics formulas and constants come from community
reverse-engineering, mainly KuromiAK's
[Uma Musume Race Mechanics](https://docs.google.com/document/d/15VzW9W2tXBBTibBRbZ8IVpW6HaMX8H0RP03kq6Az7Xg/)
document (building on work by @umamusu_reveng, @kak_eng and @hoffe_33); the glossary's terms were
collected with the help of the [uma.guide glossary](https://uma.guide/guides/glossary). No game
data is included: it's copied from your own game client by `racemech sync`.

The language model never does the maths. Every question goes through three steps:

1. **Understand** (code): skill names including typos and community shorthand (OYL, PTTM, GW,
   "kanata", "tokyo" for Tokyo Racecourse), CM number, running style, Stamina, recovery size,
   counts ("2 subdued"), and intent ("has X" vs "should I buy X"). Ambiguities become explicit
   notes ("0.35 recovery" -> 3.5%; unspecified tiers -> ○). Aliases live in
   `racemech/knowledge/aliases.yaml`; acronyms of multi-word skill names are generated.
2. **Compute and retrieve** (code): skill trigger windows on the CM's course, speed
   carryover, CM simulation numbers (simulation), the Stamina/HP model (green Stamina skills added, named debuffs sized from game data,
   with/without comparisons and a precomputed verdict and recommendation), plus the most relevant passages of a curated mechanics
   knowledge pack (BM25 keyword search, no model).
3. **Phrase** (one call to a local model via Ollama), told to use only numbers from that
   context and to say when it doesn't know.

## Data sources

| What | Where from | Online? |
|---|---|---|
| Skills (conditions, effects, durations), names, descriptions | Global game client's `master.mdb` (copied); JP client only for skills Global lacks, marked JP-only | No |
| Track names, released Champions Meetings (course, ground, season, weather) | Global `master.mdb` | No |
| Course geometry (corners, straights, slopes) | community skill data `course_data.json`, cached | Only during `racemech sync` |
| Announced / predicted Champions Meetings not in the game data yet (labelled as such) | events timeline (the one bot_repo uses), cached | Only during `racemech sync` |
| Characters: aptitudes, unique and built-in skills, default style | Global `master.mdb` | No |
| Character version names ("New Year", "Festival") for matching "NY Dia" | the character database `character-cards.json`, copied from the remote host (a scraper) or downloaded from the character database | Only during `racemech sync` |
| CM simulation data: skill fire rates, timing and win rates on real players' builds | community simulation snapshots, saved daily by bot_repo on the remote host and copied (or fetched directly as a fallback) | Only during `racemech sync` |
| Stamina model, trigger windows, accel ratings | bot_repo calculator modules, imported read-only | No |
| Condition-field reference | bot_repo checkout (`tests/skill_condition_explanation.txt`) | No |
| Mechanics knowledge | `racemech/knowledge/*.md` in this repo | No |
| Model | Ollama on `localhost` | No |

## Setup

```bash
py -3.14 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,bot]"
ollama pull qwen3.5:9b-q4_K_M
.venv/Scripts/racemech sync
```

Settings come from `racemech.toml` (copy `racemech.example.toml`) or `RACEMECH_*` environment
variables; `racemech config` prints the effective values. Nothing machine-specific is built in:
set at least `bot_repo` (a bot_repo checkout) and `global_master` (the Global client's
`master.mdb`) before the first `racemech sync`. Run `racemech sync` again after a game update.

## Use

```bash
racemech ask "How many debuffers does a late surger with 770 stamina survive in CM22?"
racemech ask --show-context "What does Moving Past, and Beyond do in CM21?"
racemech chat                       # interactive; empty line to quit
racemech context "..."              # what the model would be given, without calling it
racemech ask --model qwen3.5:4b-q4_K_M "..."   # smaller, faster, less accurate
```

By default the whole race mechanics doc (`racemech/knowledge/mechanics.md`, ~5k tokens) is part of
the system prompt, so every mechanics question can use all of it; Ollama reuses that fixed prefix,
so it costs well under a second per question. Keyword search still supplies skill, strategy,
glossary and condition-field passages. `full_mechanics = false` switches back to searching the
mechanics doc too.

| Setup (125-question eval, 2 runs) | Passed | Coverage (58) | Median s |
|---|---|---|---|
| 4B, search only | 112 | 49 | 3.0 |
| 9B, search only | 119 | 54 | 3.5 |
| 4B, whole doc | 121 / 117 | 54 / 51 | 3.4 |
| **9B, whole doc (default)** | **121 / 122** | **56 / 57** | 3.7 |

If Ollama isn't running the commands print an "unavailable" message instead of answering.

## Serving bot_repo

`racemech serve` answers questions for bot_repo (a chat channel and direct messages) over the network, in the persona's voice:

```
racemech serve                  # listens on serve_host:serve_port (default 0.0.0.0:8000)
```

- `GET /health` and `POST /ask {"question", "asker"}`; every request needs
  `Authorization: Bearer <serve_token>` (set in `racemech.toml`; the caller holds the same value). The server refuses to start without a token.
- One answer at a time; more than `serve_max_waiting` queued questions get 503 `busy`. If Ollama is
  down, `/ask` returns 503 `model_unavailable` and the caller says it can't answer right now; if the
  PC is off, the bot's health check times out and it says the same.
- Questions and answers are appended to `data/qa_log.jsonl` (on the PC only) as eval material.

Running it unattended on Windows: `scripts/racemech-hidden.vbs <command>` runs `racemech <command>`
from the repo root with no console window and appends the output to `data/<command>.log`.

- At logon: one shortcut in the Startup folder (`shell:startup`) to
  `wscript.exe "<repo>\scripts\racemech-logon.vbs"`, where `<repo>` is this checkout. It runs
  `sync` first and starts `serve` only once sync has finished, so serve never loads yesterday's
  data; if sync fails (offline, remote host down) serve still starts with the last good data.
  (Logon-triggered scheduled tasks need admin rights; the Startup folder doesn't.)
- Start or restart by hand: Task Scheduler entry `racemech\serve` (runs
  `racemech-hidden.vbs serve` on demand: `schtasks /Run /TN "racemech\serve"`); stop the old one
  first (end the `python.exe` serving port 8000). Serve reads the data only when it starts, so
  restart it after a manual `racemech sync`.

## Evaluation

`eval/questions.yaml` holds questions with checkable expectations (numbers within a
tolerance, required keywords, questions that must be declined). Every answer is also checked for
numbers that don't appear in its context (invented numbers).

```bash
racemech eval                                   # configured model
racemech eval --models "qwen3.5:4b-q4_K_M,qwen3.5:9b-q4_K_M"
racemech eval --only cm22-white-recovery,stacking
```

Reports are written to `reports/` (gitignored).

## Development

```bash
.venv/Scripts/ruff check .
.venv/Scripts/python -m pytest -q
```

Tests that need the bot checkout and synced data are marked `integration` and skip themselves
when unavailable (as in CI).

## License

MIT, see [LICENSE](LICENSE). Uma Musume and its game data belong to Cygames; this project is
unofficial and ships none of that data.
