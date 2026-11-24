# race-mechanics

The language model never does the maths. race-mechanics is a local question-answering assistant
for Uma Musume (Global) skills and race mechanics: code works out every number, and a local model
only puts the result into words.

> **Published snapshot.** This repository is a snapshot of the project. Development continues
> privately; this copy isn't updated, and issues and pull requests aren't tracked here.

**Eval:** two full runs of the 141-question eval on this code passed 137 and 141 questions
(coverage questions: 56 and 58 of 58) with `qwen3.5:9b-q4_K_M`. The latest run is in
[eval/RESULTS.md](eval/RESULTS.md); what the eval checks is described under
[Evaluation](#evaluation).

Every question goes through three steps:

1. **Understand** (code): skill names including typos and community shorthand (OYL, PTTM, GW,
   "kanata", "tokyo" for Tokyo Racecourse), CM number, running style, Stamina, recovery size,
   counts ("2 subdued"), and intent ("has X" vs "should I buy X"). Ambiguities become explicit
   notes ("0.35 recovery" -> 3.5%; unspecified tiers -> ○). Aliases live in
   `racemech/knowledge/aliases.yaml`; acronyms of multi-word skill names are generated.
2. **Compute and retrieve** (code): skill trigger windows on the CM's course, speed carryover,
   CM simulation numbers, the Stamina/HP model (green Stamina skills added, named debuffs sized
   from game data, with/without comparisons and a precomputed verdict and recommendation), plus
   the most relevant passages of a curated mechanics knowledge pack (BM25 keyword search, no
   model).
3. **Phrase** (one call to a local model via Ollama), told to use only numbers from that context
   and to say when it doesn't know.

**Knowledge files are our own writing.** `racemech/knowledge/` (mechanics, glossary, skills,
strategy) is written in our own words. The mechanics formulas and constants come from community
reverse-engineering, mainly KuromiAK's
[Uma Musume Race Mechanics](https://docs.google.com/document/d/15VzW9W2tXBBTibBRbZ8IVpW6HaMX8H0RP03kq6Az7Xg/)
document (building on work by @umamusu_reveng, @kak_eng and @hoffe_33); the glossary's terms were
collected with the help of the [uma.guide glossary](https://uma.guide/guides/glossary). No game
data is included: it's copied from your own game client by `racemech sync`.

> **Readable, not runnable on its own.** race-mechanics imports calculator modules (skill trigger
> windows, the stamina model, CM course lookup, simulation snapshot reading) from a separate
> codebase at runtime (the `bot_repo` setting), and answers from game data copied from your own
> game client; neither is part of this repo. Without them the code, knowledge files, prompts and
> eval are all here to read, and the tests that need them skip themselves, but `racemech ask` /
> `serve` / `eval` won't start.

## Data sources

| What | Where from | Online? |
|---|---|---|
| Skills (conditions, effects, durations), names, descriptions | The Global client's `master.mdb`, copied from your own game client; the JP client only for skills Global lacks, marked JP-only | No |
| Track names, released Champions Meetings (course, ground, season, weather) | The Global `master.mdb`, copied from your own game client | No |
| Characters: aptitudes, unique and built-in skills, default style | The Global `master.mdb`, copied from your own game client | No |
| Course geometry (corners, straights, slopes) | Open-source community course data, cached | Only during `racemech sync` |
| Announced / predicted Champions Meetings not in the game data yet (labelled as such) | An upcoming-events timeline, cached | Only during `racemech sync` |
| Character version names ("New Year", "Festival") | A community character database, cached | Only during `racemech sync` |
| CM simulation data: skill fire rates, timing and win rates on real players' builds | Community simulation snapshots, cached | Only during `racemech sync` |
| Stamina model, trigger windows, accel ratings | Calculator modules in the `bot_repo` codebase, imported read-only | No |
| Condition-field reference | A text file in the `bot_repo` codebase | No |
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
set at least `bot_repo` and `global_master` (the Global client's `master.mdb`) before the first
`racemech sync`. Each online source in the table above is a setting too; one left unset is
skipped and its previous copy kept. Run `racemech sync` again after a game update.

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

If Ollama isn't running the commands print an "unavailable" message instead of answering.

## Optional HTTP server

`racemech serve` answers questions for a calling application, in a configured persona (a TOML
file named by the `serve_voice` setting; see [docs/persona.example.toml](docs/persona.example.toml),
empty for plain answers). It exposes
`GET /health` and `POST /ask`, requires a bearer token on every request (it won't start without
one), and handles one question at a time; when too many are waiting it answers 503 `busy`.
Questions and answers are appended to a local log under `data/` for later evaluation. Running it
unattended on Windows is described in [docs/windows-autostart.md](docs/windows-autostart.md).

## Evaluation

`eval/questions.yaml` holds questions with checkable expectations (numbers within a tolerance,
required keywords, questions that must be declined). Every answer is also checked for numbers
that don't appear in its context (invented numbers). The latest full run is summarised in
[eval/RESULTS.md](eval/RESULTS.md).

```bash
racemech eval                                   # configured model
racemech eval --models "qwen3.5:4b-q4_K_M,qwen3.5:9b-q4_K_M"
racemech eval --only cm22-white-recovery,stacking
```

A full run rewrites `eval/RESULTS.md`; per-question reports go to `reports/` (gitignored).

## Development

```bash
.venv/Scripts/ruff check .
.venv/Scripts/python -m pytest -q
```

Tests that need the `bot_repo` codebase and synced data are marked `integration` and skip
themselves when unavailable (as in CI).

## License

MIT, see [LICENSE](LICENSE). Uma Musume and its game data belong to Cygames; this project is
unofficial and ships none of that data.
