"""Build data/iot.db (SQLite) from data/iot_telemetry.csv.

The CSV is the same IoT telemetry sample used in the Eventhouse videos:
6,000 readings from 20 sensors in 4 Canadian cities. Customers, sites and
the device table are small reference tables added for this lesson.
"""
import csv, sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / "data" / "iot.db"

CUSTOMERS = [("C-100", "Aurora Cold Chain"), ("C-200", "Prairie Grid Labs")]
SITES = {  # city -> (site_code, customer_id)
    "Toronto": ("TOR-01", "C-100"), "Montreal": ("MTL-01", "C-100"),
    "Calgary": ("CAL-01", "C-200"), "Vancouver": ("VAN-01", "C-200"),
}
BACKUPS = {"sensor-005": "sensor-004", "sensor-013": "sensor-012"}  # backup -> primary

def main() -> None:
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
      CREATE TABLE customers (customer_id TEXT PRIMARY KEY, customer_name TEXT);
      CREATE TABLE sites     (site_code TEXT PRIMARY KEY, city TEXT, customer_id TEXT);
      CREATE TABLE devices   (device_id TEXT PRIMARY KEY, site_code TEXT, backup_for TEXT);
      CREATE TABLE readings  (ts TEXT, device_id TEXT, temperature REAL, humidity REAL,
                              pressure REAL, status TEXT, PRIMARY KEY (device_id, ts));
    """)
    con.executemany("INSERT INTO customers VALUES (?, ?)", CUSTOMERS)
    con.executemany("INSERT INTO sites VALUES (?, ?, ?)", [(c, city, cu) for city, (c, cu) in SITES.items()])
    devices, rows = {}, []
    with open(HERE / "data" / "iot_telemetry.csv", newline="") as f:
        for r in csv.DictReader(f):
            devices[r["DeviceId"]] = SITES[r["Site"]][0]
            rows.append((r["Timestamp"], r["DeviceId"], float(r["Temperature"]), float(r["Humidity"]),
                         float(r["Pressure"]), r["Status"]))
    con.executemany("INSERT INTO devices VALUES (?, ?, ?)",
                    [(d, s, BACKUPS.get(d)) for d, s in sorted(devices.items())])
    con.executemany("INSERT INTO readings VALUES (?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    for t in ("customers", "sites", "devices", "readings"):
        print(f"{t:<10} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>6} rows")
    con.close()

if __name__ == "__main__":
    main()
