#!/usr/bin/env python3
"""
uartctl - UART (Universal Asynchronous Receiver–Transmitter) control tool.

Current stage:
- CLI (Command-Line Interface) skeleton using argparse
- No hardware interaction yet
"""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uartctl",
        description="UART control tool for embedded devices.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help="Subcommands",
    )

    # scan subcommand (placeholder)
    scan_parser = subparsers.add_parser(
        "scan",
        help="List available serial ports (placeholder)",
    )
    scan_parser.set_defaults(func=cmd_scan)

    return parser


def cmd_scan(_args: argparse.Namespace) -> int:
    print("scan: not implemented yet")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Dispatch to selected subcommand
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
