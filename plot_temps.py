#!/usr/bin/env python3
import csv
import datetime as dt
import math
import matplotlib.pyplot as plt
import os
from datetime import datetime


def load_csv(path: str):
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

    return t, t0, t1

def main(path: str):
    t, t0, t1 = load_csv(path)

    #plt.figure()
    #plt.figure(figsize=(14, 7))
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
    
    #plt.savefig(out_png, dpi=150)
    #plt.savefig(out_png, dpi=200)
    plt.savefig(out_png, dpi=300)

    print(f"Wrote {out_png}")

    plt.show()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} temps.csv")
        raise SystemExit(2)
    main(sys.argv[1])
