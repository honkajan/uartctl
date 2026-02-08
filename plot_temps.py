#!/usr/bin/env python3
import csv
import datetime as dt
import matplotlib.pyplot as plt
import os
from datetime import datetime


def load_csv(path: str):
    t = []
    t0 = []
    t1 = []

    with open(path, newline="", encoding="utf-8") as f:
        # Skip metadata/comment lines starting with '#'
        rows = (line for line in f if not line.startswith("#"))
        r = csv.DictReader(rows)

        for row in r:
            # Skip missing samples (if any)
            if not row["t0_C"] or not row["t1_C"]:
                continue

            # iso_time like "2026-02-04T11:39:42"
            t.append(dt.datetime.fromisoformat(row["iso_time"]))
            t0.append(float(row["t0_C"]))
            t1.append(float(row["t1_C"]))

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
