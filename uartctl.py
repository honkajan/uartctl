#!/usr/bin/env python3
"""
uartctl - UART (Universal Asynchronous Receiver–Transmitter) control tool.

Host-side CLI (Command-Line Interface) utility for communicating with an embedded
target over a serial (UART) link using a simple line-based ASCII protocol.

Subcommands:
- scan: list available serial ports (use --all to include /dev/ttyS* ports in the listing)
- ping: send "PING" and expect "PONG"
- id: query device identification string ("ID?")
- ver: query firmware version as MAJOR.MINOR.PATCH ("VER?")
- uptime: query device uptime in milliseconds ("UPTIME?"), optionally formatted with --human

Common options:
- --port <path|auto>: serial port to use, or 'auto' to select the only available candidate
  (default: auto)
- --autoall: when using --port auto, include built-in /dev/ttyS* ports as candidates
  (if this results in multiple candidates, auto-selection will fail and you must specify --port)
- --json: emit a single JSON (JavaScript Object Notation) object on stdout for scripting
- -v/--verbose: emit debug logging to stderr

Transport:
- Uses pyserial (Python serial library). Commands and responses are newline-terminated.
"""

import argparse
import sys
import time
import json
import re
import csv
import logging
from datetime import datetime
import os



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

_TEMP_KV_RE = re.compile(r"(\w+)=([0-9A-Fa-fx]+)")


def add_serial_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--port",
        default="auto",
        help="Serial port (e.g., /dev/ttyUSB0) or 'auto' (default: auto)",
    )
    p.add_argument(
        "--autoall",
        action="store_true",
        help="Port auto-select: Include built-in ttyS* ports",
    )
    p.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Baud rate (default: 115200)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Read timeout in seconds (default: 1.0)",
    )
    p.add_argument(
        "--settle-ms",
        type=int,
        default=200,
        help="Delay after opening the port (ms). Useful if device resets on open.",
    )



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

    # scan subcommand
    scan_parser = subparsers.add_parser("scan", help="List available serial ports")
    scan_parser.set_defaults(func=cmd_scan)
    scan_parser.add_argument(
        "--all",
        action="store_true",
        help="Include built-in ttyS* ports",
    )

    # ping subcommand
    ping_parser = subparsers.add_parser("ping", help="Send PING and expect PONG")
    add_serial_args(ping_parser)
    ping_parser.set_defaults(func=cmd_ping)


    # id subcommand
    id_parser = subparsers.add_parser("id", help="Query device identification string")
    add_serial_args(id_parser)
    id_parser.set_defaults(func=cmd_id)


    # ver subcommand
    ver_parser = subparsers.add_parser("ver", help="Query firmware version (MAJOR.MINOR.PATCH)")
    add_serial_args(ver_parser)
    ver_parser.set_defaults(func=cmd_ver)


    # uptime subcommand
    uptime_parser = subparsers.add_parser("uptime", help="Query device uptime in milliseconds")
    add_serial_args(uptime_parser)
    uptime_parser.add_argument(
        "--human",
        action="store_true",
        help="Print uptime in human-readable form (e.g. 1h 2m 3s)",
    )
    uptime_parser.set_defaults(func=cmd_uptime)

    # rping parser  (remote ping)
    rping_parser = subparsers.add_parser("rping", help="RF ping the remote node via the gateway")
    add_serial_args(rping_parser)
    rping_parser.set_defaults(func=cmd_rping)

    #temp parser (remote temperature)
    temp_parser = subparsers.add_parser("temp", help="Fetch remote temperatures via the gateway")
    add_serial_args(temp_parser)
    temp_parser.set_defaults(func=cmd_temp)

    # logtemp parser (CSV logger for TEMP?)
    logtemp_parser = subparsers.add_parser("logtemp", help="Log remote temperatures to CSV (Excel-friendly)")
    add_serial_args(logtemp_parser)
    logtemp_parser.add_argument("--out", default="temps.csv", help="Output CSV file (default: temps.csv)")
    logtemp_parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval seconds (default: 1.0)")
    logtemp_parser.add_argument("--count", type=int, default=None, help="Number of samples (default: unlimited until Ctrl+C)")
    logtemp_parser.set_defaults(func=cmd_logtemp)


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
        emit_ok(args, {"uptime_ms": ms, "uptime_human": human})
    else:
        print(human if args.human else ms)
    return EX_OK

def cmd_rping(args: argparse.Namespace) -> int:
    """
    RF ping the remote node via the gateway.
    UART command: RPING?
    Expected response:
      - 'RPONG'
      - or 'RPING FAIL ...'
    """
    rc, resp = uart_request_line(args, b"RPING?\n")
    if rc != EX_OK:
        if rc == EX_TIMEOUT:
            return emit_err(args, EX_TIMEOUT, "timeout waiting for RPONG")
        return rc

    if resp is None:
        return emit_err(args, EX_TIMEOUT, "timeout waiting for RPONG")

    if resp != "RPONG":
        # Pass through diagnostics from firmware
        return emit_err(args, EX_BAD_RESPONSE, f"unexpected response '{resp}' (expected 'RPONG')")

    if args.json:
        emit_ok(args, {"response": resp})
    else:
        print(resp)

    return EX_OK


def parse_temp_line(line: str) -> dict:
    """
    Parse: 'TEMP ADC0=... ADC1=... T0=... T1=... age=... flags=0x....'
    Returns a dict with numeric values (ints), flags is int.
    """
    if not line.startswith("TEMP "):
        raise ValueError(f"not a TEMP line: {line!r}")

    kv = dict(_TEMP_KV_RE.findall(line))
    if not kv:
        raise ValueError(f"no key=value fields in TEMP line: {line!r}")

    out: dict = {}
    for k, v in kv.items():
        out[k] = int(v, 0)  # base-0 handles hex with 0x prefix

    # Convenience conversions (keep originals too)
    if "T0" in out:
        out["T0_C"] = out["T0"] / 1000.0
    if "T1" in out:
        out["T1_C"] = out["T1"] / 1000.0

    return out

def resolve_out_path(out: str | None) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if out is None:
        return f"temps_{ts}.csv"

    # If user gave a filename, insert timestamp before extension
    base, ext = os.path.splitext(out)
    if ext.lower() != ".csv":
        ext = ".csv"

    return f"{base}_{ts}{ext}"

def cmd_temp(args: argparse.Namespace) -> int:
    """
    Fetch remote temperatures via the gateway.
    UART command: TEMP?
    Expected response:
      - 'TEMP ...'
      - or 'TEMP FAIL ...'
    """
    rc, resp = uart_request_line(args, b"TEMP?\n")
    if rc != EX_OK:
        if rc == EX_TIMEOUT:
            return emit_err(args, EX_TIMEOUT, "timeout waiting for TEMP response")
        return rc

    if resp is None:
        return emit_err(args, EX_TIMEOUT, "timeout waiting for TEMP response")

    if not resp.startswith("TEMP "):
        return emit_err(args, EX_BAD_RESPONSE, f"unexpected response '{resp}' (expected 'TEMP ...')")

    try:
        d = parse_temp_line(resp)
    except Exception as e:
        return emit_err(args, EX_BAD_RESPONSE, f"failed to parse TEMP response: {e}")

    if args.json:
        emit_ok(args, {
            "raw": resp,
            "adc0": d.get("ADC0"),
            "adc1": d.get("ADC1"),
            "t0_mC": d.get("T0"),
            "t1_mC": d.get("T1"),
            "t0_C": d.get("T0_C"),
            "t1_C": d.get("T1_C"),
            "age_ms": d.get("age"),
            "flags": d.get("flags"),
        })
        return EX_OK

    # Human output (robust)
    t0 = d.get("T0_C")
    t1 = d.get("T1_C")
    age = d.get("age")
    flags = d.get("flags")

    def fmt_temp(x):
        return f"{x:.2f}" if isinstance(x, (int, float)) else "N/A"

    age_str = str(age) if isinstance(age, int) else "N/A"
    flags_str = f"0x{flags:04X}" if isinstance(flags, int) else "N/A"

    print(f"T0={fmt_temp(t0)} °C  T1={fmt_temp(t1)} °C  age={age_str} ms flags={flags_str}")
    return EX_OK



def cmd_logtemp(args: argparse.Namespace) -> int:
    """
    Periodically fetch TEMP samples and write CSV for Excel/plotting.

    Output columns:
      iso_time, epoch_s, t0_C, t1_C, t0_mC, t1_mC, age_ms, flags, adc0, adc1

    Stop with Ctrl+C.
    """
    out_path = resolve_out_path(args.out)

    start_ts = time.time()
    start_iso = datetime.fromtimestamp(start_ts).isoformat(timespec="seconds")

    print("Logging temperatures")
    print(f"  start time: {start_iso}")
    print(f"  port: {args.port}")
    print(f"  interval: {args.interval} s")
    print(f"  output: {out_path}")
    print("Press Ctrl+C to stop")
    print()

    interval = float(args.interval)
    count = args.count

    # Open output file (line-buffered text)
    try:
        f = open(out_path, "w", encoding="utf-8", newline="")
    except Exception as e:
        return emit_err(args, EX_IO, f"failed to open output file '{out_path}': {e}")

    with f:
        w = csv.writer(f)
        w.writerow([f"# start_time={start_iso} interval={interval}s port={args.port}"])
        w.writerow(["iso_time", "epoch_s", "t0_C", "t1_C", "t0_mC", "t1_mC", "age_ms", "flags", "adc0", "adc1"])


        n = 0
        try:
            while True:
                if count is not None and n >= count:
                    break

                rc, resp = uart_request_line(args, b"TEMP?\n")
                ts = time.time()
                iso = datetime.fromtimestamp(ts).isoformat(timespec="seconds")

                if rc == EX_OK and resp and resp.startswith("TEMP "):
                    try:
                        d = parse_temp_line(resp)
                    except Exception:
                        d = {}

                    t0_mC = d.get("T0")
                    t1_mC = d.get("T1")
                    adc0 = d.get("ADC0")
                    adc1 = d.get("ADC1")
                    age_ms = d.get("age")
                    flags = d.get("flags")

                    t0_C = (t0_mC / 1000.0) if isinstance(t0_mC, int) else None
                    t1_C = (t1_mC / 1000.0) if isinstance(t1_mC, int) else None

                    w.writerow([iso, f"{ts:.3f}", t0_C, t1_C, t0_mC, t1_mC, age_ms,
                                f"0x{flags:04X}" if isinstance(flags, int) else None,
                                adc0, adc1])

                    if not args.json and args.verbose:
                        print(f"LOG {iso} T0={t0_C:.2f}C T1={t1_C:.2f}C", file=sys.stderr)

                else:
                    # Log a failed sample row (keep time continuity)
                    w.writerow([iso, f"{ts:.3f}", None, None, None, None, None, None, None, None])
                    if not args.json:
                        print(f"ERROR: TEMP sample failed rc={rc} resp={resp!r}", file=sys.stderr)

                f.flush()
                n += 1
                time.sleep(interval)

        except KeyboardInterrupt:
            pass

    if args.json:
        emit_ok(args, {"out": out_path, "samples": n})
    else:
        print(f"Wrote {n} samples to {out_path}")
    return EX_OK



def uart_request_line(args: argparse.Namespace, request: bytes) -> tuple[int, str | None]:
    """
    Send a request line over UART and read one response line.

    Returns: (exit_code, response_str_or_none)
    """
    if serial is None:
        return (emit_err(args, EX_SERIAL, "pyserial not installed"), None)

    port = resolve_port(args)
    # -> port is either a real port name (non-empty string) or None

    if not port:
        # auto-selection found zero or multiple candidates (or pyserial not installed)
        return (emit_err(args, EX_SERIAL, "unable to auto-select port; specify --port"), None)

    # Open serial port
    try:
        ser = serial.Serial(
            port=port,
            baudrate=args.baud,
            timeout=args.timeout,
            write_timeout=args.timeout,
        )
    except Exception as e:
        return (emit_err(args, EX_SERIAL, f"failed to open serial port '{port}': {e}"), None)
    
    logging.debug("open port=%s baud=%d timeout=%.3fs", port, args.baud, args.timeout)

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
            return (emit_err(args, EX_SERIAL, f"failed to write to '{port}': {e}"), None)
        

        try:
            raw = ser.readline()
        except Exception as e:
            return (emit_err(args, EX_SERIAL, f"failed to read from '{port}': {e}"), None)


    if not raw:
        logging.debug("rx: <timeout>")
        return (EX_TIMEOUT, None)

    resp = raw.decode("ascii", errors="replace").strip()
    logging.debug("rx: %r", resp)

    return (EX_OK, resp)

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

def resolve_port(args: argparse.Namespace) -> str | None:
    """
    Resolve serial port:
    - If args.port is a real device path, use it.
    - If args.port is 'auto' (or missing/empty), auto-select only if exactly one candidate exists.
    """

    # get stripped string or an empty string ("").
    port_arg = (getattr(args, "port", None) or "").strip()

    # return a real port name:  non-empty string that is not "auto" (e.g., /dev/ttyUSB0)
    if port_arg and port_arg.lower() != "auto":
        return port_arg
    
    # here, port_arg is either "auto" or empty string ("") -> auto-select port

    if list_ports is None:
        return None

    candidates: list[str] = []
    for p in list_ports.comports():
        dev = p.device or ""
        if not dev:
            continue # ignore invalid entries
        if not getattr(args, "autoall", False) and dev.startswith("/dev/ttyS"):
            continue # skip built-in serial ports unless --autoall is given
        candidates.append(dev)

    if len(candidates) == 1:
        return candidates[0]

    return None

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