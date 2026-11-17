#!/usr/bin/env python3
"""Generate the synthetic IoT telemetry CSV used in video 1.

Running this script with the default options reproduces
data/iot_telemetry.csv exactly: 6,000 rows, seed 7, one reading every
30 seconds starting at 2026-11-01T00:00:00Z.
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 7
ROW_COUNT = 6_000
INTERVAL = timedelta(seconds=30)
START_TIME = datetime(2026, 11, 1, tzinfo=timezone.utc)
DEVICES = [f"sensor-{i:03d}" for i in range(1, 21)]
SITES = ["Toronto", "Montreal", "Vancouver", "Calgary"]
SPIKE_PROBABILITY = 0.01
SPIKE_OFFSET_C = 15
ALERT_TEMPERATURE_C = 32
COLUMNS = [
    "Timestamp",
    "DeviceId",
    "Site",
    "Temperature",
    "Humidity",
    "Pressure",
    "Status",
]


def build_rows(seed: int = SEED, row_count: int = ROW_COUNT) -> list[tuple]:
    """Return telemetry rows that match the bundled sample when defaults are used."""
    rng = random.Random(seed)
    site_of = {device: rng.choice(SITES) for device in DEVICES}

    rows: list[tuple] = []
    timestamp = START_TIME
    for _ in range(row_count):
        device = rng.choice(DEVICES)
        temperature = round(rng.gauss(22, 3), 2)
        if rng.random() < SPIKE_PROBABILITY:
            temperature = round(temperature + SPIKE_OFFSET_C, 2)
        humidity = round(rng.uniform(30, 70), 1)
        pressure = round(rng.gauss(1013, 4), 1)
        status = "ALERT" if temperature > ALERT_TEMPERATURE_C else "OK"
        rows.append(
            (
                timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                device,
                site_of[device],
                temperature,
                humidity,
                pressure,
                status,
            )
        )
        timestamp += INTERVAL
    return rows


def write_csv(path: Path, rows: list[tuple]) -> None:
    # The bundled file uses CRLF so a byte-for-byte comparison stays simple.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "iot_telemetry.csv",
        help="Output CSV path (defaults to data/iot_telemetry.csv).",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--rows", type=int, default=ROW_COUNT)
    args = parser.parse_args()

    rows = build_rows(seed=args.seed, row_count=args.rows)
    write_csv(args.output, rows)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
