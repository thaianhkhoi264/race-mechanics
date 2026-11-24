# Project Rules — race-mechanics

## Publishing / data hygiene

This repo must stay safe to make public at any time, so nothing that belongs to
the game or to the community ever enters it.

- **No game data in the repo or in its history.** That means `master.mdb` copies,
  extracted skill/course/character JSON, simulation snapshots, community-site dumps, and
  anything else `racemech sync` fetches. Sync writes into a gitignored data
  directory; it is never committed.
- **`racemech/knowledge/*.md` must be our own writing.** If a passage was copied
  or closely adapted from a community-written document, replace it with our own
  summary or a citation. Do not vendor someone else's doc, even partially.
- **No local layout leaks.** `racemech.toml` stays out; `racemech.example.toml`
  is the only committed config. No absolute paths, tokens, API keys or webhook
  URLs anywhere, including in test fixtures.
- **Before any public push**, check the full history, not just the working tree:
  `git log --stat` and `git log --all --diff-filter=A --name-only` for data files
  that were added and later deleted. A deleted file is still in the history.
- **Keep the eval harness and a results summary committed.** The 141-question
  eval (`eval/questions.yaml`) is ours and contains no third-party content.
  Per-run reports (`reports/`, full model answers) stay gitignored; each run's
  pass/coverage/latency summary goes in a single committed `eval/RESULTS.md`.
- If in doubt about a file, leave it out and ask.

## Repo conventions

- Keep `pyproject.toml` as the single source of dependencies and entry points.
- Tests that need the bot_repo codebase, synced data, or a running Ollama
  must stay behind the `integration` / `llm` markers and skip cleanly without them.
- Run `ruff` before committing.
