#!/usr/bin/env python3
"""
uartctl - UART (Universal Asynchronous Receiver–Transmitter) control tool.

Current stage:
- CLI (Command-Line Interface) skeleton using argparse
- No hardware interaction yet
"""

import argparse
import sys
import time


try:
    import serial  # pyserial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

EX_OK = 0
EX_SERIAL = 10
EX_TIMEOUT = 11
EX_BAD_RESPONSE = 12


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

    # ping subcommand
    ping_parser = subparsers.add_parser(
        "ping",
        help="Send PING and expect PONG",
    )
    ping_parser.add_argument("--port", required=True, help="Serial port (e.g., /dev/ttyUSB0)")
    ping_parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    ping_parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds (default: 1.0)")
    ping_parser.add_argument(
        "--settle-ms",
        type=int,
        default=200,
        help="Delay after opening the port (ms). Useful if device resets on open.",
    )
    ping_parser.set_defaults(func=cmd_ping)

    # id subcommand
    id_parser = subparsers.add_parser(
        "id",
        help="Query device identification string",
    )
    id_parser.add_argument("--port", required=True, help="Serial port (e.g., /dev/ttyUSB0)")
    id_parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    id_parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds")
    id_parser.add_argument(
        "--settle-ms",
        type=int,
        default=200,
        help="Delay after opening the port (ms)",
    )
    id_parser.set_defaults(func=cmd_id)

    # ver subcommand
    ver_parser = subparsers.add_parser(
        "ver",
        help="Query firmware version (MAJOR.MINOR.PATCH)",
    )
    ver_parser.add_argument("--port", required=True, help="Serial port (e.g., /dev/ttyUSB0)")
    ver_parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    ver_parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds")
    ver_parser.add_argument(
        "--settle-ms",
        type=int,
        default=200,
        help="Delay after opening the port (ms)",
    )
    ver_parser.set_defaults(func=cmd_ver)





    return parser

def cmd_scan(args: argparse.Namespace) -> int:
    if list_ports is None:
        print("ERROR: pyserial is not installed (cannot scan ports).", file=sys.stderr)
        print("Hint: activate venv and run: pip install pyserial", file=sys.stderr)
        return EX_SERIAL

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

def cmd_ping(args: argparse.Namespace) -> int:
    if serial is None:
        print("ERROR: pyserial is not installed (cannot use ping).", file=sys.stderr)
        print("Hint: activate venv and run: pip install pyserial", file=sys.stderr)
        return EX_SERIAL

    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            timeout=args.timeout,
            write_timeout=args.timeout,
        )
    except Exception as e:
        print(f"ERROR: failed to open serial port '{args.port}': {e}", file=sys.stderr)
        return EX_SERIAL

    with ser:
        # Optional settle time (some boards reset when DTR toggles on open)
        if args.settle_ms > 0:
            time.sleep(args.settle_ms / 1000.0)

        # Clear any old data
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        # Send PING
        try:
            ser.write(b"PING\n")
            ser.flush()
        except Exception as e:
            print(f"ERROR: failed to write to '{args.port}': {e}", file=sys.stderr)
            return EX_SERIAL

        # Read one line response
        try:
            raw = ser.readline()  # reads until '\n' or timeout
        except Exception as e:
            print(f"ERROR: failed to read from '{args.port}': {e}", file=sys.stderr)
            return EX_SERIAL

    if not raw:
        print("ERROR: timeout waiting for response.", file=sys.stderr)
        return EX_TIMEOUT

    resp = raw.decode("ascii", errors="replace").strip()
    if resp != "PONG":
        print(f"ERROR: unexpected response: '{resp}' (expected 'PONG')", file=sys.stderr)
        return EX_BAD_RESPONSE

    print("PONG")
    return EX_OK

def cmd_id(args: argparse.Namespace) -> int:
    rc, resp = uart_request_line(args, b"ID?\n")
    if rc != EX_OK:
        if rc == EX_TIMEOUT:
            print("ERROR: timeout waiting for ID response.", file=sys.stderr)
        return rc
    assert resp is not None
    print(resp)
    return EX_OK


def cmd_ver(args: argparse.Namespace) -> int:
    rc, resp = uart_request_line(args, b"VER?\n")
    if rc != EX_OK:
        if rc == EX_TIMEOUT:
            print("ERROR: timeout waiting for version response.", file=sys.stderr)
        return rc

    assert resp is not None
    parts = resp.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        print(f"ERROR: unexpected version format: '{resp}' (expected MAJOR.MINOR.PATCH)", file=sys.stderr)
        return EX_BAD_RESPONSE

    # Normalize (e.g., "00.02.000" -> "0.2.0")
    major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
    print(f"{major}.{minor}.{patch}")
    return EX_OK


def uart_request_line(args: argparse.Namespace, request: bytes) -> tuple[int, str | None]:
    """
    Send a request line over UART and read one response line.

    Returns: (exit_code, response_str_or_none)
    """
    if serial is None:
        print("ERROR: pyserial is not installed.", file=sys.stderr)
        return (EX_SERIAL, None)

    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            timeout=args.timeout,
            write_timeout=args.timeout,
        )
    except Exception as e:
        print(f"ERROR: failed to open serial port '{args.port}': {e}", file=sys.stderr)
        return (EX_SERIAL, None)

    with ser:
        if getattr(args, "settle_ms", 0) > 0:
            time.sleep(args.settle_ms / 1000.0)

        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        try:
            ser.write(request)
            ser.flush()
        except Exception as e:
            print(f"ERROR: failed to write to '{args.port}': {e}", file=sys.stderr)
            return (EX_SERIAL, None)

        try:
            raw = ser.readline()
        except Exception as e:
            print(f"ERROR: failed to read from '{args.port}': {e}", file=sys.stderr)
            return (EX_SERIAL, None)

    if not raw:
        return (EX_TIMEOUT, None)

    resp = raw.decode("ascii", errors="replace").strip()
    return (EX_OK, resp)



def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Dispatch to selected subcommand
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
