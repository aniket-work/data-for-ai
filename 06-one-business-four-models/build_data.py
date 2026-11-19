"""Generate the sample data for the fictional bike-share "Harbourline Bikes" (city of Port Ellery)
and load it into DuckDB. Deterministic: the same seed always gives the same data.
Everything here is made up. Riders are IDs only (no names or other personal data)."""
import csv, random, datetime as dt, pathlib, duckdb

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"; DATA.mkdir(exist_ok=True)
AS_OF = dt.datetime(2026, 6, 30, 18, 0)          # "now" for every rule and question in the lesson
rnd = random.Random(7)

STATIONS = [  # id, name, capacity, bikes available right now
    ("ST-01", "Harbour Front", 24, 11), ("ST-02", "Market Square", 20, 2), ("ST-03", "Old Mill", 16, 1),
    ("ST-04", "City Library", 18, 7), ("ST-05", "Riverside Park", 22, 9), ("ST-06", "Tech Campus", 20, 5),
    ("ST-07", "Museum Row", 14, 4), ("ST-08", "North Ferry", 16, 2)]
BIKES = [(f"B-{i:03d}", "ebike" if i % 3 == 0 else "classic") for i in range(1, 43)]   # 14 e-bikes, 28 classic
RIDERS = [f"R-{i:03d}" for i in range(1, 61)]
MEMBERSHIPS = []
for i, r in enumerate(RIDERS, 1):
    kind = "annual" if rnd.random() < 0.45 else "casual"
    start = dt.date(2025, 7, 1) + dt.timedelta(days=rnd.randint(0, 300))
    MEMBERSHIPS.append((f"M-{i:03d}", r, kind, start.isoformat()))
kind_of = {m[1]: m[2] for m in MEMBERSHIPS}
bike_type = dict(BIKES)

def fare(kind, btype, minutes, status):
    if status == "cancelled": return 0.0
    if kind == "annual": return round(0.10 * minutes, 2) if btype == "ebike" else 0.0
    return round(1.25 + (0.25 if btype == "ebike" else 0.12) * minutes, 2)

TRIPS = []
start_day = dt.datetime(2026, 4, 15, 6, 0)
weights = [5, 4, 2, 3, 4, 3, 2, 3]               # busier stations start more trips
active = rnd.sample(RIDERS, 44)                  # 16 riders have not ridden since mid-May
for i in range(1, 1201):
    rider = rnd.choice(active if i > 520 else RIDERS)
    t0 = start_day + dt.timedelta(minutes=rnd.randint(0, 76 * 24 * 60))
    if t0 > AS_OF - dt.timedelta(minutes=60): t0 -= dt.timedelta(days=3)
    if i > 520 and t0 < AS_OF - dt.timedelta(days=45): t0 += dt.timedelta(days=30)
    if rider not in active and t0 > dt.datetime(2026, 5, 15): t0 -= dt.timedelta(days=40)
    bike = rnd.choice(BIKES)[0]
    s_from = rnd.choices(STATIONS, weights)[0][0]
    s_to = rnd.choices(STATIONS, list(reversed(weights)))[0][0]
    status = "cancelled" if rnd.random() < 0.04 else "completed"
    minutes = rnd.randint(0, 1) if status == "cancelled" else rnd.randint(4, 38)
    TRIPS.append((f"TR-{i:04d}", rider, bike, s_from, s_to, t0.isoformat(timespec="minutes"), minutes,
                  fare(kind_of[rider], bike_type[bike], minutes, status), status))
TRIPS.sort(key=lambda t: t[5])
TRIPS = [(f"TR-{i:04d}",) + t[1:] for i, t in enumerate(TRIPS, 1)]   # number trips in time order

def write(name, header, rows):
    with open(DATA / name, "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)

write("stations.csv", ["station_id", "name", "capacity", "available_bikes"], STATIONS)
write("bikes.csv", ["bike_id", "bike_type"], BIKES)
write("riders.csv", ["rider_id"], [(r,) for r in RIDERS])
write("memberships.csv", ["membership_id", "rider_id", "membership_type", "start_date"], MEMBERSHIPS)
write("trips.csv", ["trip_id", "rider_id", "bike_id", "start_station_id", "end_station_id", "start_ts",
                    "duration_min", "fare_cad", "status"], TRIPS)

db = HERE / "bikeshare.duckdb"
if db.exists(): db.unlink()
con = duckdb.connect(str(db))
for t in ["stations", "bikes", "riders", "memberships", "trips"]:
    con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_csv_auto('{(DATA / (t + '.csv')).as_posix()}', header=true)")
for t in ["stations", "bikes", "riders", "memberships", "trips"]:
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t:<12} {n:>5} rows")
print(f"Loaded data/*.csv into bikeshare.duckdb  (as of {AS_OF:%Y-%m-%d %H:%M}, all data fictional)")
