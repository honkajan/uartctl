#!/usr/bin/env python3
"""
uartctl - UART (Universal Asynchronous Receiver–Transmitter) control tool.

Current stage:
- CLI (Command-Line Interface) skeleton using argparse
- No hardware interaction yet
"""

import argparse
import sys

try:
    from serial.tools import list_ports  # pyserial
except ImportError:
    list_ports = None


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
    
    scan_parser.add_argument(
        "--all",
        action="store_true",
        help="Include built-in ttyS* ports",
    )


    return parser

def cmd_scan(args: argparse.Namespace) -> int:
    if list_ports is None:
        print("ERROR: pyserial is not installed (cannot scan ports).", file=sys.stderr)
        print("Hint: activate venv and run: pip install pyserial", file=sys.stderr)
        return 10

    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return 0

    shown = 0
    for p in ports:
        # Typical fields:
        # p.device: /dev/ttyUSB0, /dev/ttyACM0
        # p.description: adapter/board description
        # p.hwid: USB VID:PID and serial, etc.
        dev = p.device or ""
        if not args.all and dev.startswith("/dev/ttyS"):
            continue

        desc = p.description or ""
        hwid = p.hwid or ""
        print(f"{dev}\t{desc}\t{hwid}")
        shown += 1

    if shown == 0:
        print("No serial ports found.")

    return 0



def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Dispatch to selected subcommand
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
