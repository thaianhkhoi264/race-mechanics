"""Command-line entry point: ``racemech <command>``."""
from __future__ import annotations

import argparse
import sys

from racemech import __version__
from racemech.config import load_settings


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="racemech", description=__doc__)
    p.add_argument("--version", action="version", version=f"racemech {__version__}")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("config", help="print the effective settings")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "config":
        for k, v in vars(load_settings()).items():
            print(f"{k} = {v}")
        return 0
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
