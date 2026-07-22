"""Command-line interface for the bootstrapped project."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


STATUS_MESSAGE = (
    "Project bootstrapped. X collection, database integration, and LLM "
    "integration are not implemented."
)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="x-signal-finder",
        description="Ethplorer X Signal Finder project CLI.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "status",
        help="Show the current implementation status without external API calls.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "status":
        print(STATUS_MESSAGE)
        return 0

    parser.print_help()
    return 0
