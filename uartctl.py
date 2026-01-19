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
import json
import logging



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

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON (JavaScript Object Notation)",
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
    ping_parser.add_argument(
        "--port",
        default="auto",
        help="Serial port (e.g., /dev/ttyUSB0) or 'auto' (default: auto)",
    )
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
    id_parser.add_argument(
        "--port",
        default="auto",
        help="Serial port (e.g., /dev/ttyUSB0) or 'auto' (default: auto)",
    )
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
    ver_parser.add_argument(
        "--port",
        default="auto",
        help="Serial port (e.g., /dev/ttyUSB0) or 'auto' (default: auto)",
    )
    ver_parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    ver_parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds")
    ver_parser.add_argument(
        "--settle-ms",
        type=int,
        default=200,
        help="Delay after opening the port (ms)",
    )
    ver_parser.set_defaults(func=cmd_ver)

    # uptime subcommand
    uptime_parser = subparsers.add_parser(
        "uptime",
        help="Query device uptime in milliseconds",
    )
    uptime_parser.add_argument(
        "--port",
        default="auto",
        help="Serial port (e.g., /dev/ttyUSB0) or 'auto' (default: auto)",
    )
    uptime_parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    uptime_parser.add_argument("--timeout", type=float, default=1.0, help="Read timeout in seconds")
    uptime_parser.add_argument(
        "--settle-ms",
        type=int,
        default=200,
        help="Delay after opening the port (ms)",
    )
    uptime_parser.add_argument(
        "--human",
        action="store_true",
        help="Print uptime in human-readable form (e.g. 1h 2m 3s)",
    )

    uptime_parser.set_defaults(func=cmd_uptime)




    return parser

def cmd_scan(args: argparse.Namespace) -> int:
    if list_ports is None:
        return emit_err(args, EX_SERIAL, "pyserial not installed (cannot scan ports)")

    ports = list(list_ports.comports())

    if args.json:
        items = []
        for p in ports:
            dev = p.device or ""
            if not args.all and dev.startswith("/dev/ttyS"):
                continue

            items.append(
                {
                    "device": dev,
                    "description": p.description or "",
                    "hwid": p.hwid or "",
                }
            )

        payload = {"ports": items}

        if not items:
            payload["note"] = "no serial ports found"

        emit_ok(args, payload)
        return EX_OK

    # Human output
    if not ports:
        print("No serial ports found.")
        return EX_OK

    shown = 0
    for p in ports:
        dev = p.device or ""
        if not args.all and dev.startswith("/dev/ttyS"):
            continue

        desc = p.description or ""
        hwid = p.hwid or ""
        print(f"{dev}\t{desc}\t{hwid}")
        shown += 1

    if shown == 0:
        print("No serial ports found.")

    return EX_OK

def resolve_port(args: argparse.Namespace) -> str | None:
    """
    Resolve serial port:
    - If args.port is a real device path, use it.
    - If args.port is 'auto' (or missing/empty), auto-select only if exactly one candidate exists.
    """
    port_arg = (getattr(args, "port", None) or "").strip()

    # Treat missing port as auto (if you set default="auto", this is always set)
    if port_arg and port_arg.lower() != "auto":
        return port_arg

    if list_ports is None:
        return None

    candidates: list[str] = []
    for p in list_ports.comports():
        dev = p.device or ""
        if not dev:
            continue
        if not getattr(args, "all", False) and dev.startswith("/dev/ttyS"):
            continue
        candidates.append(dev)

    if len(candidates) == 1:
        return candidates[0]

    return None


def uart_request_line(args: argparse.Namespace, request: bytes) -> tuple[int, str | None]:
    """
    Send a request line over UART and read one response line.

    Returns: (exit_code, response_str_or_none)
    """
    if serial is None:
        return (emit_err(args, EX_SERIAL, "pyserial not installed"), None)

    port = resolve_port(args)
    if not port:
        # Provide a helpful message
        requested = (getattr(args, "port", "") or "").strip().lower()
        if requested == "auto" or requested == "":
            return (emit_err(args, EX_SERIAL, "unable to auto-select port; specify --port"), None)
        return (emit_err(args, EX_SERIAL, f"invalid port '{args.port}'"), None)


    try:
        ser = serial.Serial(
            port=port,
            baudrate=args.baud,
            timeout=args.timeout,
            write_timeout=args.timeout,
        )
    except Exception as e:
        return (emit_err(args, EX_SERIAL, f"failed to open serial port '{args.port}': {e}"), None)
    
    logging.debug("open port=%s baud=%d timeout=%.3fs", args.port, args.baud, args.timeout)

    with ser:
        if getattr(args, "settle_ms", 0) > 0:
            time.sleep(args.settle_ms / 1000.0)

        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        logging.debug("tx: %r", request)

        try:
            ser.write(request)
            ser.flush()
        except Exception as e:
            return (emit_err(args, EX_SERIAL, f"failed to write to '{args.port}': {e}"), None)
        

        try:
            raw = ser.readline()
        except Exception as e:
            return (emit_err(args, EX_SERIAL, f"failed to read from '{args.port}': {e}"), None)


    if not raw:
        logging.debug("rx: <timeout>")
        return (EX_TIMEOUT, None)

    resp = raw.decode("ascii", errors="replace").strip()
    logging.debug("rx: %r", resp)

    return (EX_OK, resp)

def format_uptime_human(ms: int) -> str:
    seconds = ms // 1000
    ms_rem = ms % 1000

    minutes, sec = divmod(seconds, 60)
    hours, min_ = divmod(minutes, 60)

    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if min_:
        parts.append(f"{min_}m")
    if sec or not parts:
        parts.append(f"{sec}s")

    # Include milliseconds only if under 1 second
    if hours == 0 and min_ == 0 and sec < 10 and ms_rem:
        parts[-1] = f"{sec}.{ms_rem:03d}s"

    return " ".join(parts)

def emit_ok(args: argparse.Namespace, payload: dict) -> None:
    if args.json:
        out = {"ok": True, "command": args.command}
        out.update(payload)
        print(json.dumps(out))
    else:
        # Non-JSON callers should print their normal output themselves.
        # So emit_ok does nothing in that mode.
        pass


def emit_err(args: argparse.Namespace, code: int, message: str) -> int:
    if args.json:
        out = {"ok": False, "command": args.command, "error": message, "code": int(code)}
        print(json.dumps(out))
    else:
        print(f"ERROR: {message}", file=sys.stderr)
    return int(code)


def cmd_ping(args: argparse.Namespace) -> int:

    rc, resp = uart_request_line(args, b"PING\n")
    if rc != EX_OK:
        if rc == EX_TIMEOUT:
            return emit_err(args, EX_TIMEOUT, "timeout waiting for PONG")
        return rc
    
    if resp is None:
        return emit_err(args, EX_TIMEOUT, "timeout waiting for PONG")
    
    if resp != "PONG":
        return emit_err(args, EX_BAD_RESPONSE, f"unexpected response '{resp}' (expected 'PONG')")

    if args.json:
        emit_ok(args, {"response": "PONG"})
    else:
        print("PONG")
    return EX_OK

def cmd_id(args: argparse.Namespace) -> int:
    rc, resp = uart_request_line(args, b"ID?\n")
    if rc != EX_OK:
        if rc == EX_TIMEOUT:
            return emit_err(args, EX_TIMEOUT, "timeout waiting for ID response")
        return rc
    
    if resp is None:
        return emit_err(args, EX_TIMEOUT, "timeout waiting for ID response")
    
    if args.json:
        emit_ok(args, {"id": resp})
    else:
        print(resp)
    return EX_OK


def cmd_ver(args: argparse.Namespace) -> int:
    rc, resp = uart_request_line(args, b"VER?\n")
    if rc != EX_OK:
        if rc == EX_TIMEOUT:
            return emit_err(args, EX_TIMEOUT, "timeout waiting for version response")
        return rc

    if resp is None:
        return emit_err(args, EX_TIMEOUT, "timeout waiting for version response")

    parts = resp.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return emit_err(args, EX_BAD_RESPONSE, f"unexpected version format '{resp}' (expected MAJOR.MINOR.PATCH)")

    # Normalize (e.g., "00.02.000" -> "0.2.0")
    major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
    ver_norm = f"{major}.{minor}.{patch}"

    if args.json:
        emit_ok(args, {"version": ver_norm, "major": major, "minor": minor, "patch": patch})
    else:
        print(ver_norm)
    return EX_OK

def cmd_uptime(args: argparse.Namespace) -> int:
    rc, resp = uart_request_line(args, b"UPTIME?\n")
    if rc != EX_OK:
        if rc == EX_TIMEOUT:
            return emit_err(args, EX_TIMEOUT, "timeout waiting for uptime response")
        return rc

    if resp is None:
        return emit_err(args, EX_TIMEOUT, "timeout waiting for uptime response")

    if not resp.isdigit():
        return emit_err(args, EX_BAD_RESPONSE, f"unexpected uptime format '{resp}' (expected integer ms)")

    ms = int(resp)
    human = format_uptime_human(ms)

    if args.json:
        payload = {"uptime_ms": ms}
        if args.human:
            payload["uptime_human"] = human
        emit_ok(args, payload)
    else:
        print(human if args.human else ms)
    return EX_OK

def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="DEBUG: %(message)s")


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)

    # Dispatch to selected subcommand
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
