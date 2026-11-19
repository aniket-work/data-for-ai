"""Build data/iot.duckdb from data/iot_telemetry.csv.

Same IoT telemetry as the Ossie ontology (folder 03) and semantic model (folder 04)
lessons: 6,000 readings from 20 sensors in 4 Canadian cities. The sites table gets
two extra columns for this lesson: a site manager name (personal data, so the
governance layer protects it) and an on-call channel (the approved way to escalate).
All names are fictional.
"""
from pathlib import Path
import duckdb

HERE = Path(__file__).parent
DB = HERE / "data" / "iot.duckdb"
CSV = HERE / "data" / "iot_telemetry.csv"

CUSTOMERS = [("C-100", "Aurora Cold Chain"), ("C-200", "Prairie Grid Labs")]
SITES = [  # site_code, city, customer_id, site_manager (fictional), on_call_channel
    ("TOR-01", "Toronto", "C-100", "Lea Tremblay", "#oncall-tor"),
    ("MTL-01", "Montreal", "C-100", "Omar Haddad", "#oncall-mtl"),
    ("CAL-01", "Calgary", "C-200", "Priya Nair", "#oncall-cal"),
    ("VAN-01", "Vancouver", "C-200", "Ben Carter", "#oncall-van"),
]
BACKUPS = {"sensor-005": "sensor-004", "sensor-013": "sensor-012"}  # backup -> primary

def main() -> None:
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("CREATE TABLE customers (customer_id VARCHAR PRIMARY KEY, customer_name VARCHAR)")
    con.execute("""CREATE TABLE sites (site_code VARCHAR PRIMARY KEY, city VARCHAR, customer_id VARCHAR,
                   site_manager VARCHAR, on_call_channel VARCHAR)""")
    con.executemany("INSERT INTO customers VALUES (?, ?)", CUSTOMERS)
    con.executemany("INSERT INTO sites VALUES (?, ?, ?, ?, ?)", SITES)
    con.execute(f"""
      CREATE TABLE readings AS
      SELECT CAST(Timestamp AS TIMESTAMP) AS ts, DeviceId AS device_id, Site AS city,
             Temperature AS temperature, Humidity AS humidity, Pressure AS pressure, Status AS status
      FROM read_csv('{CSV.as_posix()}', header = true, timestampformat = '%Y-%m-%dT%H:%M:%SZ')""")
    con.execute("""
      CREATE TABLE devices AS
      SELECT DISTINCT r.device_id, s.site_code, CAST(NULL AS VARCHAR) AS backup_for
      FROM readings r JOIN sites s USING (city) ORDER BY 1""")
    con.execute("ALTER TABLE readings DROP COLUMN city")
    for backup, primary in BACKUPS.items():
        con.execute("UPDATE devices SET backup_for = ? WHERE device_id = ?", [primary, backup])
    for t in ("customers", "sites", "devices", "readings"):
        print(f"{t:<10} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>6} rows")
    con.close()

if __name__ == "__main__":
    main()
