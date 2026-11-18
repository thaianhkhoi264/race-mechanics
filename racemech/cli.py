"""Command-line entry point: ``racemech <command>``."""
from __future__ import annotations

import argparse
import sys

from racemech import __version__, data_sync
from racemech.config import load_settings
from racemech.llm import ModelUnavailable

UNAVAILABLE = "The assistant is unavailable right now (the local model isn't running)."


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="racemech", description=__doc__)
    p.add_argument("--version", action="version", version=f"racemech {__version__}")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("config", help="print the effective settings")
    sync = sub.add_parser("sync", help="copy the game databases and refresh course geometry")
    sync.add_argument("--offline", action="store_true",
                      help="skip the course geometry and CM timeline downloads")

    for name, help_ in (("ask", "answer one question"), ("chat", "ask questions interactively")):
        sp = sub.add_parser(name, help=help_)
        if name == "ask":
            sp.add_argument("question", nargs="+")
        sp.add_argument("--model", help="Ollama model tag (overrides the setting)")
        sp.add_argument("--show-context", action="store_true", help="print what the model was given")
    ctx = sub.add_parser("context", help="show the context for a question without calling the model")
    ctx.add_argument("question", nargs="+")
    ev = sub.add_parser("eval", help="run the evaluation set against one or more models")
    ev.add_argument("--models", help="comma-separated Ollama tags (default: the configured model)")
    ev.add_argument("--only", help="comma-separated question ids")
    return p


def _print_answer(ans, show_context: bool) -> None:
    if show_context:
        print("=" * 72 + "\n" + ans.context.render() + "\n" + "=" * 72)
    print(ans.reply.text)
    r = ans.reply
    print(f"\n[{r.model} · {r.seconds:.1f}s · {r.prompt_tokens} prompt + {r.output_tokens} output tokens]",
          file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.command == "config":
        for k, v in vars(settings).items():
            print(f"{k} = {v}")
        return 0
    if args.command == "sync":
        for item, status in data_sync.sync(settings.data_dir, settings.global_master, settings.jp_master,
                                           download_courses=not args.offline):
            print(f"{item:20} {status}")
        return 0
    if args.command == "context":
        from racemech.assistant import Assistant
        print(Assistant(settings).builder.build(" ".join(args.question)).render())
        return 0
    if args.command == "eval":
        from racemech import evaluation
        from racemech.assistant import Assistant
        from racemech.config import REPO_ROOT
        models = args.models.split(",") if args.models else [settings.model]
        only = set(args.only.split(",")) if args.only else None
        questions = evaluation.load_questions()
        summaries = []
        for model in models:
            assistant = Assistant(settings, model.strip())
            if not assistant.client.available():
                print(UNAVAILABLE)
                return 2
            print(f"\n=== {model}")
            scores = evaluation.run(assistant, questions, only)
            path = evaluation.write_report(model, scores, REPO_ROOT / "reports")
            summaries.append(evaluation.summary(model, scores))
            print(f"report: {path}")
        print("\nmodel".ljust(66) + "passed  invented  median s  by category")
        for s in summaries:
            print(f"{s['model']:65} {s['passed']:>2}/{s['total']:<3} {s['with_invented_numbers']:>6}"
                  f"  {s['median_seconds']:8.1f}  {s['by_category']}")
        return 0
    if args.command in ("ask", "chat"):
        from racemech.assistant import Assistant
        assistant = Assistant(settings, args.model)
        if not assistant.client.available():
            print(UNAVAILABLE)
            return 2
        if args.command == "ask":
            try:
                _print_answer(assistant.ask(" ".join(args.question)), args.show_context)
            except ModelUnavailable:
                print(UNAVAILABLE)
                return 2
            return 0
        print(f"racemech chat ({assistant.client.model}). Empty line or Ctrl+C to quit.")
        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not q:
                return 0
            try:
                _print_answer(assistant.ask(q), args.show_context)
            except ModelUnavailable:
                print(UNAVAILABLE)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
