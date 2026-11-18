"""Command-line entry point: ``racemech <command>``."""
from __future__ import annotations

import argparse
import sys

from racemech import __version__, data_sync
from racemech.config import load_settings


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="racemech", description=__doc__)
    p.add_argument("--version", action="version", version=f"racemech {__version__}")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("config", help="print the effective settings")
    sync = sub.add_parser("sync", help="copy the game databases and refresh course geometry")
    sync.add_argument("--offline", action="store_true", help="skip the course geometry download")
    return p


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
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
