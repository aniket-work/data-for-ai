"""Builds the fictional "Alder & Finch Outdoor" operational database in PostgreSQL.

Three legacy systems, three schemas, cryptic column names (the kind a VKG hides):
  crm.cst_mstr   customers (IDs only, no personal data)
  erp.sup_mstr   suppliers        erp.prd_mstr  products
  erp.ord_hdr    order headers    erp.ord_ln    order lines
  svc.wrty_tkt   warranty tickets from the service desk
Everything is fictional and generated with a fixed seed.
Usage: python db/build_data.py  [--dsn postgresql://vkg@127.0.0.1:5432/alderfinch]
"""
import argparse, random, datetime as dt, io, time
import psycopg

TODAY = dt.datetime(2026, 11, 20, 9, 0)          # "now" for the lesson
SEED = 18
DDL = """
DROP SCHEMA IF EXISTS crm CASCADE; DROP SCHEMA IF EXISTS erp CASCADE; DROP SCHEMA IF EXISTS svc CASCADE;
CREATE SCHEMA crm; CREATE SCHEMA erp; CREATE SCHEMA svc;
CREATE TABLE crm.cst_mstr (cst_id varchar(10) PRIMARY KEY, rgn_cd char(2) NOT NULL, tier_cd char(1) NOT NULL, crt_dt date NOT NULL);
CREATE TABLE erp.sup_mstr (sup_id varchar(6) PRIMARY KEY, sup_nm varchar(60) NOT NULL, ctry_cd char(2) NOT NULL);
CREATE TABLE erp.prd_mstr (sku varchar(12) PRIMARY KEY, prd_desc varchar(80) NOT NULL, cat_cd char(3) NOT NULL,
                           sup_id varchar(6) NOT NULL REFERENCES erp.sup_mstr, list_px numeric(8,2) NOT NULL);
CREATE TABLE erp.ord_hdr (ord_no varchar(10) PRIMARY KEY, cst_id varchar(10) NOT NULL REFERENCES crm.cst_mstr,
                          ord_dt date NOT NULL, chnl_cd char(3) NOT NULL);
CREATE TABLE erp.ord_ln  (ord_no varchar(10) NOT NULL REFERENCES erp.ord_hdr, ln_no smallint NOT NULL,
                          sku varchar(12) NOT NULL REFERENCES erp.prd_mstr, qty smallint NOT NULL, unit_px numeric(8,2) NOT NULL,
                          PRIMARY KEY (ord_no, ln_no));
CREATE TABLE svc.wrty_tkt (tkt_id varchar(10) PRIMARY KEY, ord_no varchar(10) NOT NULL REFERENCES erp.ord_hdr,
                           sku varchar(12) NOT NULL REFERENCES erp.prd_mstr, opn_ts timestamp NOT NULL,
                           sts_cd char(1) NOT NULL, iss_cd varchar(8) NOT NULL, cls_ts timestamp);
"""
SUPPLIERS = [("SUP-01", "Northpine Textiles", "CA"), ("SUP-02", "Harrow Gas Works", "DE"), ("SUP-03", "Ridgeway Shelter Works", "PT"),
             ("SUP-04", "Lumen Loft Down", "VN"), ("SUP-05", "Cobblestone Packs", "CA"), ("SUP-06", "Tallgrass Shelters", "US")]
# (category, supplier, base price, names)
CATALOG = {
    "TNT": [("SUP-03", 389, ["Ridgeline 2P Tent", "Ridgeline 3P Tent", "Summit Dome 2P", "Summit Dome 4P"]),
            ("SUP-06", 329, ["Prairie Trek 2P", "Prairie Trek 3P", "Bivy Lite 1P", "Basecamp 6P"])],
    "PCK": [("SUP-05", 159, ["Trailhead 28L", "Trailhead 38L", "Longhaul 55L", "Longhaul 65L", "Daytrip 18L", "Summit 45L"]),
            ("SUP-01", 139, ["Canopy 30L", "Canopy 40L", "Ferry 22L", "Ferry 32L"])],
    "STV": [("SUP-02", 89, ["Pocket Burner", "Pocket Burner Ti", "Twin Ring Stove", "Basecamp Range", "Windshield Kit", "Simmer Pro"])],
    "SLB": [("SUP-04", 219, ["Lumen -5C Bag", "Lumen -10C Bag", "Lumen 0C Quilt", "Lumen Summer Bag", "Lumen Duo Bag"]),
            ("SUP-01", 149, ["Canopy Synthetic -5C", "Canopy Synthetic 5C", "Canopy Kids Bag", "Canopy Liner", "Canopy XL -7C"])],
}
ISSUES = {"TNT": ["SEAM", "POLE", "ZIP"], "PCK": ["ZIP", "STRAP"], "STV": ["VALVE", "IGNIT"], "SLB": ["ZIP", "LOFT"]}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dsn", default="postgresql://vkg@127.0.0.1:5432/alderfinch")
    ap.add_argument("--customers", type=int, default=12000); ap.add_argument("--orders", type=int, default=60000)
    a = ap.parse_args(); rnd = random.Random(SEED); t0 = time.time()
    prods = []
    for cat, groups in CATALOG.items():
        for sup, base, names in groups:
            for i, nm in enumerate(names):
                prods.append((f"{cat}-{sup[-2:]}{i+1:02d}", nm, cat, sup, round(base * (0.8 + 0.1 * i), 2)))
    custs = [(f"C{n:06d}", rnd.choice(["ON", "QC", "BC", "AB", "NS", "MB"]), rnd.choice("BBBSSG"),
              TODAY.date() - dt.timedelta(days=rnd.randint(30, 2400))) for n in range(1, a.customers + 1)]
    orders, lines, tickets = [], [], []
    for n in range(1, a.orders + 1):
        c = rnd.choice(custs); d = TODAY.date() - dt.timedelta(days=rnd.randint(1, 540))
        ono = f"SO{n:07d}"; orders.append((ono, c[0], d, rnd.choice(["WEB", "WEB", "STR", "APP"])))
        for ln in range(1, rnd.choice([1, 1, 2, 2, 3, 4]) + 1):
            p = rnd.choice(prods); lines.append((ono, ln, p[0], rnd.choice([1, 1, 1, 2]), p[4]))
            # warranty tickets: ~3% of lines; Ridgeway tents (SUP-03) bought in the last 120 days have a seam problem
            risk = 0.03 + (0.22 if p[3] == "SUP-03" and (TODAY.date() - d).days < 120 else 0)
            if rnd.random() < risk:
                opened = dt.datetime.combine(d, dt.time(10)) + dt.timedelta(days=rnd.randint(3, 60), minutes=rnd.randint(0, 600))
                if opened >= TODAY: opened = TODAY - dt.timedelta(hours=rnd.randint(2, 200))
                iss = "SEAM" if p[3] == "SUP-03" and risk > 0.1 else rnd.choice(ISSUES[p[2]])
                age = (TODAY - opened).days
                status = "O" if (age < 45 and rnd.random() < 0.75) else rnd.choice("CCCW")
                closed = None if status == "O" else min(TODAY, opened + dt.timedelta(days=rnd.randint(2, 30)))
                if status == "O" and p[3] == "SUP-03": opened = min(opened, TODAY - dt.timedelta(days=rnd.randint(5, 40)))
                tickets.append((f"T{len(tickets)+1:06d}", ono, p[0], opened, status, iss, closed))
    with psycopg.connect(a.dsn, autocommit=True) as con:
        con.execute(DDL)
        def copy(tbl, rows):
            with con.cursor().copy(f"COPY {tbl} FROM STDIN") as cp:
                for r in rows: cp.write_row(r)
        copy("crm.cst_mstr", custs); copy("erp.sup_mstr", SUPPLIERS); copy("erp.prd_mstr", prods)
        copy("erp.ord_hdr", orders); copy("erp.ord_ln", lines); copy("svc.wrty_tkt", tickets)
        con.execute("CREATE INDEX ON erp.ord_ln (sku); CREATE INDEX ON svc.wrty_tkt (sku); CREATE INDEX ON svc.wrty_tkt (ord_no); "
                    "CREATE INDEX ON erp.ord_hdr (cst_id); ANALYZE;")
        size = con.execute("SELECT pg_size_pretty(sum(pg_total_relation_size(c.oid))) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                           "WHERE n.nspname IN ('crm','erp','svc') AND c.relkind='r'").fetchone()[0]
    print(f"Alder & Finch Outdoor (fictional) loaded in {time.time()-t0:.1f} s, seed {SEED}, today {TODAY:%Y-%m-%d}")
    for t, rows in [("crm.cst_mstr", custs), ("erp.sup_mstr", SUPPLIERS), ("erp.prd_mstr", prods), ("erp.ord_hdr", orders),
                    ("erp.ord_ln", lines), ("svc.wrty_tkt", tickets)]:
        print(f"  {t:<14} {len(rows):>8,} rows")
    print(f"  total size on disk (tables + indexes): {size}")

if __name__ == "__main__":
    main()
