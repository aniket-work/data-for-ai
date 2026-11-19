"""Generate the fictional data for one flight disruption at "Larkspur Air", a made-up regional airline
flying between two made-up jurisdictions, Norland and Solmara. Deterministic (fixed seed).
Passengers are IDs only: no names, contact details or other personal data."""
import csv, json, random, pathlib

HERE = pathlib.Path(__file__).parent; DATA = HERE / "data"; DATA.mkdir(exist_ok=True)
rnd = random.Random(11)
DAY = "2026-11-12"

AIRPORTS = [("NOR-1", "Norport", "Norland"), ("NOR-2", "Elkfield", "Norland"), ("NOR-3", "Brightwater", "Norland"),
            ("SOL-1", "Solmara City", "Solmara"), ("SOL-2", "Port Vale", "Solmara")]
FLIGHTS = [  # flight, from, to, departs, arrives, crew, seats free, status
    ("F-210", "NOR-1", "SOL-1", f"{DAY}T07:10", f"{DAY}T08:40", "C-3", 0, "scheduled"),
    ("F-214", "NOR-1", "SOL-1", f"{DAY}T14:00", f"{DAY}T15:30", "C-7", 6, "scheduled"),
    ("F-218", "NOR-1", "SOL-1", "2026-11-13T07:00", "2026-11-13T08:30", "C-4", 40, "scheduled"),
    ("F-330", "SOL-1", "SOL-2", f"{DAY}T16:30", f"{DAY}T17:20", "C-5", 12, "scheduled"),
    ("F-332", "SOL-1", "SOL-2", f"{DAY}T15:50", f"{DAY}T16:40", "C-6", 10, "scheduled"),
    ("F-500", "NOR-1", "NOR-3", f"{DAY}T07:05", f"{DAY}T07:55", "C-8", 3, "scheduled")]
CREWS = [  # crew, base, duty hours already logged today, status
    ("C-3", "NOR-1", 1.0, "assigned"), ("C-4", "NOR-1", 0.0, "assigned"), ("C-5", "SOL-1", 3.0, "assigned"),
    ("C-6", "SOL-1", 4.5, "assigned"), ("C-7", "NOR-1", 11.5, "assigned"), ("C-8", "NOR-1", 2.5, "assigned"),
    ("C-9", "NOR-1", 2.0, "reserve"), ("C-10", "SOL-1", 1.0, "reserve")]

# 36 passengers booked on F-210
PAX = []
onward = {4: "F-330", 9: "F-330", 15: "F-330", 22: "F-330", 7: "F-332", 13: "F-332", 30: "F-332"}
gold = {3, 7, 11, 19, 25, 33}
assist = {6, 28}
for i in range(1, 37):
    PAX.append(dict(passenger_id=f"P-{i:03d}", home_jurisdiction="Norland" if rnd.random() < 0.6 else "Solmara",
                    tier="gold" if i in gold else "standard", needs_assistance="yes" if i in assist else "no",
                    onward_flight=onward.get(i, "")))
with open(DATA / "passengers.csv", "w", newline="") as f:
    w = csv.DictWriter(f, PAX[0].keys()); w.writeheader(); w.writerows(PAX)

BOOK = []
for p in PAX:
    BOOK.append([p["passenger_id"], "F-210", "NOR-1", "SOL-1", round(rnd.uniform(140, 320), 2), "yes"])
# --- data-quality problems for the agent to find (deliberate, fictional)
BOOK.append(list(BOOK[11]))                       # P-012 booked twice (exact duplicate row)
BOOK[19][2] = "nor-1"                             # P-020 airport code in the wrong case
BOOK[26][4] = -189.0                              # P-027 negative fare
BOOK[4][5] = ""; BOOK[17][5] = ""                 # P-005, P-018 no contact on file
BOOK.append(["P-031", "F-500", "NOR-1", "NOR-3", 96.0, "yes"])   # P-031 on two flights at the same time
with open(DATA / "bookings.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["passenger_id", "flight_id", "origin", "destination", "fare_cad", "contact_on_file"]); w.writerows(BOOK)

def write(name, header, rows):
    with open(DATA / name, "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
write("airports.csv", ["airport_id", "name", "jurisdiction"], AIRPORTS)
write("flights.csv", ["flight_id", "origin", "destination", "departs", "arrives", "crew_id", "seats_free", "status"], FLIGHTS)
write("crews.csv", ["crew_id", "base", "duty_hours_logged", "status"], CREWS)

# --- the live operations event stream for the morning of the disruption
EV = [("05:52:10", "weather_alert", {"airport": "NOR-1", "detail": "freezing rain expected 06:30-11:00"}),
      ("06:05:31", "gate_change", {"flight": "F-500", "gate": "B4"}),
      ("06:12:02", "delay", {"flight": "F-500", "minutes": 25, "airport": "NOR-1"}),
      ("06:18:44", "booking_update", {"passenger": "P-014", "change": "seat 12C"}),
      ("06:24:09", "delay", {"flight": "F-210", "minutes": 40, "airport": "NOR-1"}),
      ("06:27:50", "delay", {"flight": "F-218", "minutes": 0, "airport": "NOR-1", "detail": "de-icing check"}),
      ("06:31:15", "runway_status", {"airport": "NOR-1", "detail": "runway 2 closed for de-icing"}),
      ("06:36:02", "delay", {"flight": "F-214", "minutes": 15, "airport": "NOR-1"}),
      ("06:40:00", "cancellation", {"flight": "F-210", "reason": "freezing rain, aircraft de-icing limit"}),
      ("06:41:22", "crew_duty_update", {"crew": "C-7", "duty_hours_logged": 11.5}),
      ("06:43:05", "seat_release", {"flight": "F-214", "seats_free": 6}),
      ("06:47:40", "booking_update", {"passenger": "P-021", "change": "meal request"})]
with open(DATA / "events.jsonl", "w") as f:
    for i, (t, typ, d) in enumerate(EV, 1):
        f.write(json.dumps({"event_id": f"E-{i:03d}", "ts": f"{DAY}T{t}", "type": typ, **d}) + "\n")
print(f"  airports {len(AIRPORTS)}  flights {len(FLIGHTS)}  crews {len(CREWS)}  passengers {len(PAX)}  bookings {len(BOOK)}  events {len(EV)}")
print("Wrote data/*.csv and data/events.jsonl  (Larkspur Air, fictional; passengers are IDs only)")
