#!/usr/bin/env python3
"""
plot_temps - Temperature log plotting utility.

Host-side helper script for plotting temperature CSV logs produced by
`uartctl logtemp`.

Input:
- CSV file written by the `logtemp` subcommand
- Expected columns include:
  - iso_time
  - t0_C, t1_C
  - flags
  - adc0, adc1

Behavior:
- Parses logged temperature samples and plots T0 and T1 versus time
- Skips clearly invalid reboot/startup rows
- Respects per-channel validity flags from firmware:
  - bit0 = T0 valid
  - bit1 = T1 valid
- Invalid channel samples are plotted as gaps (NaN), not as zero values

Optional filtering:
- `--max-rate-c-per-s` applies an optional slew-rate filter
- Samples that change faster than the given °C/s threshold are treated
  as implausible spikes and plotted as gaps

Output:
- Displays the plot interactively
- Saves a timestamped PNG alongside the input CSV
"""


import argparse
import csv
import datetime as dt
import math
import matplotlib.pyplot as plt
import os
from datetime import datetime


def apply_rate_limit(times, values, max_rate_c_per_s):
    """Replace implausibly fast jumps with NaN.

    Comparison is made against the last accepted finite point.
    NaN samples are preserved and do not update the reference point.
    """
    if max_rate_c_per_s is None:
        return values

    filtered = []
    last_t = None
    last_v = None

    for t, v in zip(times, values):
        if math.isnan(v):
            filtered.append(float("nan"))
            continue

        if last_t is None or last_v is None:
            filtered.append(v)
            last_t = t
            last_v = v
            continue

        dt_s = (t - last_t).total_seconds()
        if dt_s <= 0:
            filtered.append(float("nan"))
            continue

        rate_c_per_s = abs(v - last_v) / dt_s
        if rate_c_per_s > max_rate_c_per_s:
            filtered.append(float("nan"))
            # Keep last accepted sample unchanged
            continue

        filtered.append(v)
        last_t = t
        last_v = v

    return filtered


def load_csv(path: str, max_rate_c_per_s=None):
    """Load a uartctl logtemp CSV file and return time-aligned T0/T1 series.

    Per-channel validity flags are respected. Invalid samples are converted
    to NaN so they render as gaps in the plot. An optional slew-rate filter
    can be applied after loading.
    """
    
    t = []
    t0 = []
    t1 = []

    TEMP_FLAG_T0_VALID = 1 << 0
    TEMP_FLAG_T1_VALID = 1 << 1

    with open(path, newline="", encoding="utf-8") as f:
        rows = (line for line in f if not line.startswith("#"))
        r = csv.DictReader(rows)

        for row in r:
            flags_s = (row.get("flags") or "").strip().lower()
            adc0 = (row.get("adc0") or "").strip()
            adc1 = (row.get("adc1") or "").strip()

            # Skip clearly invalid reboot/startup rows
            if flags_s == "0x0000":
                continue

            try:
                flags = int(flags_s, 0) if flags_s else 0
            except ValueError:
                flags = 0

            # Parse raw CSV values first
            t0_c = float(row["t0_C"]) if row.get("t0_C") else float("nan")
            t1_c = float(row["t1_C"]) if row.get("t1_C") else float("nan")

            # Extra guard for known bogus zero startup row
            if (
                t0_c == 0.0 and
                t1_c == 0.0 and
                adc0 == "0" and
                adc1 == "0"
            ):
                continue

            # Respect per-channel validity bits from firmware
            if (flags & TEMP_FLAG_T0_VALID) == 0:
                t0_c = float("nan")

            if (flags & TEMP_FLAG_T1_VALID) == 0:
                t1_c = float("nan")

            # Skip row only if both channels are invalid/missing
            if math.isnan(t0_c) and math.isnan(t1_c):
                continue

            t.append(dt.datetime.fromisoformat(row["iso_time"]))
            t0.append(t0_c)
            t1.append(t1_c)

    # Optional plausibility filter for slow thermal systems
    t0 = apply_rate_limit(t, t0, max_rate_c_per_s)
    t1 = apply_rate_limit(t, t1, max_rate_c_per_s)

    return t, t0, t1


def main(path: str, max_rate_c_per_s=None):
    t, t0, t1 = load_csv(path, max_rate_c_per_s=max_rate_c_per_s)

    plt.figure(figsize=(16, 8))
    plt.plot(t, t0, label="T0 (radiator 1)")
    plt.plot(t, t1, label="T1 (radiator 2)")
    plt.xlabel("Time")
    plt.ylabel("Temperature (°C)")
    plt.title("Bathroom radiator temperatures")
    plt.grid(True)
    plt.legend()

    # --- save figure with timestamp ---
    base, _ = os.path.splitext(path)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_png = f"{base}_plot_{ts}.png"

    plt.tight_layout()
    plt.savefig(out_png, dpi=300)

    print(f"Wrote {out_png}")

    plt.show()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Plot logged temperature CSV data")
    ap.add_argument("csv_path", help="Input CSV file produced by uartctl logtemp")
    ap.add_argument(
        "--max-rate-c-per-s",
        type=float,
        default=None,
        help="Optional maximum allowed temperature slew rate in °C/s; faster jumps are plotted as gaps",
    )
    args = ap.parse_args()

    main(args.csv_path, max_rate_c_per_s=args.max_rate_c_per_s)