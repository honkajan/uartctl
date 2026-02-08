# uartctl

`uartctl` is a small host-side CLI (Command-Line Interface) utility for communicating
with an embedded target over a serial (UART – Universal Asynchronous Receiver–Transmitter)
connection.

It is intended as a practical bench/debug tool and as a learning exercise in
building robust embedded tooling with a clean protocol, predictable UX, and
script-friendly output.

---

## Features

- Line-based ASCII protocol over UART
- Subcommands for common device queries:
  - `scan`   – list available serial ports
  - `ping`   – basic connectivity check
  - `id`     – query device identification string
  - `ver`    – query firmware version
  - `uptime` – query device uptime
- Automatic serial port selection:
  - default auto-selection
  - explicit `--port auto`
  - `--autoall` to include built-in `/dev/ttyS*` ports
- Optional JSON (JavaScript Object Notation) output for scripting
- Optional verbose logging (`--verbose`) to stderr
- Human-readable uptime formatting

---

## Requirements

- Python 3.10 or newer
- `pyserial`

Install dependencies (preferably in a virtual environment):

```sh
pip install pyserial
```

---

## Usage

General form:

```sh
python uartctl.py [GLOBAL OPTIONS] <command> [COMMAND OPTIONS]
```

### Global options

- `--json`  
  Emit a single JSON object on stdout (machine-readable).

- `-v`, `--verbose`  
  Enable debug logging to stderr.

---

## Commands

### `scan`

List available serial ports.

```sh
python uartctl.py scan
```

Include built-in serial ports (`/dev/ttyS*`):

```sh
python uartctl.py scan --all
```

JSON output:

```sh
python uartctl.py --json scan
```

---

### `ping`

Check basic connectivity with the device.

**Protocol:**
- TX: `PING`
- RX: `PONG`

```sh
python uartctl.py ping --port /dev/ttyUSB0
```

Auto-select port:

```sh
python uartctl.py ping --port auto
```

---

### `id`

Query the device identification string.

**Protocol:**
- TX: `ID?`
- RX: `<device-identification-string>`

```sh
python uartctl.py id --port auto
```

---

### `ver`

Query firmware version.

**Protocol:**
- TX: `VER?`
- RX: `MAJOR.MINOR.PATCH`

```sh
python uartctl.py ver --port auto
```

---

### `uptime`

Query device uptime in milliseconds.

**Protocol:**
- TX: `UPTIME?`
- RX: `<milliseconds-since-boot>`

```sh
python uartctl.py uptime --port auto
```

Human-readable formatting:

```sh
python uartctl.py uptime --port auto --human
```

---

## Serial Port Selection

- `--port <path>`  
  Use an explicit serial device (e.g. `/dev/ttyUSB0`).

- `--port auto` (default)  
  Automatically select the port **only if exactly one candidate exists**.

- `--autoall`  
  When auto-selecting, include built-in `/dev/ttyS*` ports as candidates.
  If this results in multiple candidates, auto-selection fails and `--port`
  must be specified explicitly.

---

## Protocol Summary

The device protocol is intentionally simple and human-readable:

- ASCII text
- One command per line
- Newline-terminated (`\n`)
- One-line response per command

| Command  | Description           | Response format      |
|----------|-----------------------|----------------------|
| `PING`   | Connectivity check    | `PONG`               |
| `ID?`    | Device identification | Free-form string     |
| `VER?`   | Firmware version      | `MAJOR.MINOR.PATCH`  |
| `UPTIME?`| Device uptime         | Decimal milliseconds |

---

## Versioning

This project follows simple semantic-style versioning.
The `v0.1` tag represents the first stable, feature-complete iteration
of the tool.

---

## License

This project is licensed under the MIT License.  
See the LICENSE file for details.