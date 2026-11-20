"""Generate the raw (bronze) files for the fictional ferry operator "Saltmarsh Ferries".

Three ticket-office exports for October 2026, each with its own quirks, plus a routes reference file.
Everything here is fictional. Run:  python data/make_raw_data.py
"""
import csv, json, random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "lake" / "raw"
random.seed(9)

ROUTES = [
    {"route_code": "SM-01", "name": "Harbourfront - Gull Island", "minutes": 25, "active": True},
    {"route_code": "SM-02", "name": "Harbourfront - Cedar Point", "minutes": 40, "active": True},
    {"route_code": "SM-03", "name": "Cedar Point - Fogg Bay", "minutes": 30, "active": True},
    {"route_code": "SM-04", "name": "Gull Island - Fogg Bay", "minutes": 20, "active": True},
]
BASE = {"ADULT": 12.50, "CHILD": 6.25, "SENIOR": 9.50, "BIKE": 4.00, "VEHICLE": 38.00}
MULT = {"SM-01": 1.0, "SM-02": 1.4, "SM-03": 1.2, "SM-04": 0.8}
MIX = ["ADULT"] * 50 + ["CHILD"] * 14 + ["SENIOR"] * 12 + ["BIKE"] * 10 + ["VEHICLE"] * 14
# which routes each ticket office sells, with weights
OFFICES = {
    "harbourfront": [("SM-01", 0.55), ("SM-02", 0.45)],
    "cedarpoint":   [("SM-02", 0.40), ("SM-03", 0.60)],
    "gullisland":   [("SM-01", 0.35), ("SM-04", 0.65)],
}
PER_DAY = {"harbourfront": 62, "cedarpoint": 41, "gullisland": 34}

def tickets(office, prefix, start, days, seed_shift=0):
    rows, n = [], 0
    for d in range(days):
        day = start + timedelta(days=d)
        weekend = day.weekday() >= 5
        for _ in range(int(PER_DAY[office] * (1.35 if weekend else 1.0) * random.uniform(0.85, 1.15))):
            n += 1
            r = random.choices([c for c, _ in OFFICES[office]], [w for _, w in OFFICES[office]])[0]
            t = random.choice(MIX)
            ts = day.replace(hour=random.randint(6, 20), minute=random.choice(range(0, 60, 5)), second=0)
            rows.append(dict(ticket_id=f"{prefix}-{seed_shift + n:06d}", sold_at=ts, route=r, ticket_type=t,
                             fare=round(BASE[t] * MULT[r] * 4) / 4))
    return rows

def write(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    oct1 = datetime(2026, 10, 1)
    # 1) Harbourfront office: clean ISO timestamps and plain numbers
    hf = tickets("harbourfront", "HF", oct1, 31)
    write(RAW / "tickets_harbourfront_2026-10.csv", ["ticket_id", "sold_at", "route", "ticket_type", "fare"],
          [[r["ticket_id"], r["sold_at"].strftime("%Y-%m-%d %H:%M:%S"), r["route"], r["ticket_type"], f"{r['fare']:.2f}"] for r in hf])
    # 2) Cedar Point office: US-style dates, "$" in fares, lower-case padded route codes, Title-case ticket types
    cp = tickets("cedarpoint", "CP", oct1, 31)
    write(RAW / "tickets_cedarpoint_2026-10.csv", ["ticket_id", "sold_at", "route", "ticket_type", "fare"],
          [[r["ticket_id"], r["sold_at"].strftime("%m/%d/%Y %H:%M"), f" {r['route'].lower()}", r["ticket_type"].title(), f"${r['fare']:.2f}"] for r in cp])
    # 3) Gull Island office: re-exported days (duplicates), a few blank fares, a typo route code
    gi = tickets("gullisland", "GI", oct1, 31)
    out = []
    for r in gi:
        fare = "" if random.random() < 0.012 else f"{r['fare']:.2f}"
        route = "SM-4" if (r["route"] == "SM-04" and random.random() < 0.01) else r["route"]
        out.append([r["ticket_id"], r["sold_at"].strftime("%Y-%m-%d %H:%M:%S"), route, r["ticket_type"], fare])
    dup_days = {"2026-10-11", "2026-10-25"}
    out += [row for row in out if row[1][:10] in dup_days]           # the POS re-sent two days
    out.sort(key=lambda row: row[1])
    write(RAW / "tickets_gullisland_2026-10.csv", ["ticket_id", "sold_at", "route", "ticket_type", "fare"], out)
    (RAW / "routes.json").write_text(json.dumps(ROUTES, indent=2) + "\n")
    for p in sorted(RAW.iterdir()):
        print(f"{p.relative_to(ROOT)}  {sum(1 for _ in open(p)) - (1 if p.suffix == '.csv' else 0)} lines")

def new_batch():
    """Nov 1: the Harbourfront office got a POS update. 'fare' is now 'price_cad', and a new seasonal route shows up."""
    inc = ROOT / "lake" / "incoming"; inc.mkdir(parents=True, exist_ok=True)
    random.seed(11)
    rows = tickets("harbourfront", "HF", datetime(2026, 11, 1), 1, seed_shift=2100)
    data = []
    for i, r in enumerate(rows):
        route = "SM-05" if i % 9 == 4 else r["route"]
        data.append([r["ticket_id"], r["sold_at"].strftime("%Y-%m-%d %H:%M:%S"), route, r["ticket_type"], f"{r['fare']:.2f}"])
    p = inc / "tickets_harbourfront_2026-11-01.csv"
    write(p, ["ticket_id", "sold_at", "route", "ticket_type", "price_cad"], data)
    print(f"new batch landed: {p.relative_to(ROOT)}  ({len(data)} rows)")

if __name__ == "__main__":
    import sys
    new_batch() if "--new-batch" in sys.argv else main()
