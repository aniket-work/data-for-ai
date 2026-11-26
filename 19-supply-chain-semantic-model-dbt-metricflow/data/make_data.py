"""Generate the fictional Ostrawind Supply Co. warehouse (all names and numbers are made up).

Writes data/csv/*.csv and loads them into warehouse/ostrawind.duckdb (schema supply_chain).
Deterministic: same seed, same data.
"""
import csv, random, datetime as dt
from pathlib import Path
import duckdb

SEED = 19
TODAY = dt.date(2026, 11, 20)          # data cut-off
START = dt.date(2026, 1, 5)
rng = random.Random(SEED)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "csv"
OUT.mkdir(parents=True, exist_ok=True)

def d(x): return x.isoformat() if x else ""

suppliers = [
 # id, name, tier, country, category, region, contract, terms, onboarded, city
 ("SUP-01","Pangrove Polymer Ltd","Strategic","Canada","Polymers & Packaging","North America","CTR-PGV-2025",45,"2019-04-01","Hamilton ON"),
 ("SUP-02","Kessling Fastener GmbH","Strategic","Germany","Fasteners","Europe","CTR-KSF-2024",60,"2018-09-15","Hamburg DE"),
 ("SUP-03","Siravan Hydraulics Inc","Preferred","USA","Hydraulics","North America","CTR-SRV-2025",30,"2021-02-01","Toledo OH"),
 ("SUP-04","Tollmere Electrical Supply","Preferred","Canada","Electrical","North America","CTR-TLM-2024",30,"2020-06-10","Mississauga ON"),
 ("SUP-05","Brackenfield Timber Co","Approved","Canada","Lumber","North America","CTR-BRK-2023",30,"2017-03-20","Prince George BC"),
 ("SUP-06","Quillon Safety Gear","Approved","USA","Safety","North America","CTR-QLN-2025",45,"2022-01-12","Columbus OH"),
 ("SUP-07","Marrowgate Adhesives","Approved","USA","Adhesives & Sealants","North America","CTR-MRG-2024",30,"2020-11-03","Buffalo NY"),
 ("SUP-08","Veltrane Pipe & Valve","Preferred","Mexico","Plumbing","North America","CTR-VLT-2025",60,"2023-05-08","Monterrey MX"),
]
SUP = {s[0]: s for s in suppliers}

warehouses = [
 ("WH-TOR","Toronto Distribution Center","Toronto","East","Distribution Center",9000),
 ("WH-MTL","Montreal Distribution Center","Montreal","East","Distribution Center",6500),
 ("WH-CGY","Calgary Distribution Center","Calgary","West","Distribution Center",5200),
 ("WH-VAN","Vancouver Fulfilment Center","Vancouver","West","Fulfilment Center",4100),
]
carriers = [
 ("CAR-01","Northline Freight","Truckload",95, 2.6),
 ("CAR-02","Bluewater Intermodal","Intermodal",90, 5.5),
 ("CAR-03","Ridgeback LTL","LTL",92, 3.4),
 ("CAR-04","Cinderpath Express","Expedited",97, 1.4),
 ("CAR-05","Harrow Rail Logistics","Rail",88, 6.5),
]
CAR = {c[0]: c for c in carriers}

catalog = {
 "SUP-01": [("Polyethylene Stretch Film 18in","A",42.0,14),("HDPE Pallet Wrap 20in","A",48.5,14),("Bubble Cushion Roll 24in","B",31.0,14),
            ("Polypropylene Strapping Kit","B",56.0,14),("Moisture Barrier Bag Pack","C",22.0,14)],
 "SUP-02": [("Hex Bolt M12 Box","A",18.0,28),("Stainless Lag Screw Box","A",24.0,28),("Anchor Wedge Kit","B",36.0,28),("Lock Nut Assortment","C",14.0,28)],
 "SUP-03": [("Hydraulic Hose 3/8in 50ft","A",88.0,21),("Quick Coupler Set","B",64.0,21),("Gear Pump 12cc","A",310.0,21),("Seal Kit Universal","C",19.0,21)],
 "SUP-04": [("Copper Wire 12AWG 250ft","A",96.0,10),("LED High Bay 150W","B",142.0,10),("Breaker 20A Single Pole","B",11.5,10),("Conduit EMT 3/4in 10ft","C",8.2,10)],
 "SUP-05": [("Spruce Stud 2x4x8","A",6.4,12),("Plywood Sheathing 7/16","A",28.0,12),("Cedar Fence Board","C",4.1,12)],
 "SUP-06": [("Hard Hat Class E","B",21.0,9),("Cut Resistant Gloves A4","A",9.5,9),("Safety Glasses Clear","C",4.4,9)],
 "SUP-07": [("Construction Adhesive 28oz","A",7.9,8),("Polyurethane Sealant","B",9.8,8),("Epoxy Anchor Cartridge","B",29.0,8)],
 "SUP-08": [("PEX Pipe 1/2in 100ft","A",54.0,25),("Brass Ball Valve 3/4in","B",17.5,25),("PVC Elbow 2in Pack","C",12.0,25)],
}
products = []
n = 1001
for sid, items in catalog.items():
    for name, abc, cost, lead in items:
        products.append((f"SKU-{n}", name, SUP[sid][4], abc, round(cost*1.38,2), cost, lead, sid, round(rng.uniform(0.4, 24.0),1)))
        n += 1
PROD = {p[0]: p for p in products}
assert len(products) == 29

# which warehouses stock which sku
stocking = {p[0]: sorted(rng.sample([w[0] for w in warehouses], rng.choice([3,3,4,4,2]))) for p in products}
for p in products:                       # Pangrove film is stocked everywhere, Toronto is its hub
    if p[7] == "SUP-01": stocking[p[0]] = [w[0] for w in warehouses]

def in_incident(day):                    # Pangrove extrusion line outage window (see docs)
    return dt.date(2026,7,9) <= day <= dt.date(2026,9,26)

def ontime_prob(sid, promised):
    if sid == "SUP-01":
        if in_incident(promised): return 0.40
        if promised.month == 10: return 0.88
        return 0.95
    if sid == "SUP-03": return 0.91
    if sid == "SUP-02": return 0.975
    return 0.965

def fill_ratio(sid, promised):
    if sid == "SUP-01" and in_incident(promised): return rng.choice([1.0, 0.95, 0.9, 0.85, 0.8, 1.0])
    return 1.0 if rng.random() < 0.88 else rng.choice([0.98, 0.95])

pos, ships = [], []
span = (dt.date(2026,11,15) - START).days
weights = {"SUP-01": 3.0, "SUP-02": 1.4, "SUP-03": 1.2}
sku_w = [weights.get(p[7], 1.0) for p in products]
for i in range(600):
    p = rng.choices(products, sku_w)[0]
    sku, sid, cost, lead = p[0], p[7], p[5], p[6]
    order = START + dt.timedelta(days=rng.randint(0, span))
    promised = order + dt.timedelta(days=lead)
    wh = rng.choice(stocking[sku])
    qty = rng.choice([40, 60, 80, 100, 120, 150, 200, 250]) * (3 if p[3] == "A" else 1)
    po_id = f"PO-{26000 + i + 1}"
    status, received, qrec = "Open", None, None
    if rng.random() < 0.02:
        status = "Cancelled"
    else:
        late = rng.random() >= ontime_prob(sid, promised)
        delay = rng.randint(1, 3) if not (sid == "SUP-01" and in_incident(promised)) else rng.randint(3, 16)
        arrive = promised - dt.timedelta(days=rng.randint(0, 3)) if not late else promised + dt.timedelta(days=delay)
        if arrive <= TODAY:
            received, status = arrive, "Closed"
            qrec = int(round(qty * fill_ratio(sid, promised)))
        elif arrive - dt.timedelta(days=4) <= TODAY:
            status = "In Transit"
    pos.append([po_id, order, promised, received, sid, sku, wh, qty, qrec if received else (0 if status!="Cancelled" else None), cost, status])
    if status in ("Closed", "In Transit"):
        if sid == "SUP-01" and in_incident(promised) and rng.random() < 0.45:
            car = "CAR-04"                       # expedited recovery loads
        elif SUP[sid][3] == "Germany":
            car = "CAR-02"
        else:
            car = rng.choice(["CAR-01","CAR-01","CAR-03","CAR-05","CAR-02"])
        transit = max(1, int(round(rng.gauss(CAR[car][4], 0.9))))
        if received:
            delivered = received
            ship_date = delivered - dt.timedelta(days=transit)
            good = qrec
            dmg_rate = 0.003
            dmg = sum(1 for _ in range(qty) if rng.random() < dmg_rate)
            st = "Delivered"
        else:
            delivered, ship_date, good, dmg, st = None, TODAY - dt.timedelta(days=rng.randint(0,3)), 0, 0, "In Transit"
        w = PROD[sku][8]
        rate = {"CAR-04": 0.95, "CAR-01": 0.21, "CAR-03": 0.30, "CAR-05": 0.12, "CAR-02": 0.17}[car]
        freight = round(qty * w * rate * rng.uniform(0.9, 1.1) + 120, 2)
        ships.append([f"SHP-{70000 + len(ships) + 1}", po_id, car, ship_date, delivered, good, dmg, freight, st, SUP[sid][9], wh])

# carrier lane performance: monthly aggregate of delivered shipments per carrier and lane (origin -> warehouse city)
WCITY = {w[0]: w[2] for w in warehouses}
perf = {}
for s in ships:
    if not s[4]: continue
    car, month = s[2], s[4].replace(day=1)
    lane = f"{s[9].split(' ')[0]} -> {WCITY[s[10]]}"
    k = (car, lane, month)
    rec = perf.setdefault(k, [0, 0, 0, 0])
    transit = (s[4] - s[3]).days
    rec[0] += 1
    std = round(CAR[car][4]) + 1
    late = transit > std or (car == "CAR-01" and dt.date(2026, 8, 1) <= s[4] <= dt.date(2026, 9, 15) and rng.random() < 0.35)
    rec[1] += 0 if late else 1
    rec[2] += 1 if s[6] > 0 else 0
    rec[3] += transit
perf_rows = []
for j, ((car, lane, month), r) in enumerate(sorted(perf.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1]))):
    perf_rows.append([f"CPF-{j+1:04d}", car, lane, month, r[0], r[1], r[2], round(r[3]/r[0], 2)])

# month-end inventory snapshots (Jan-Oct) per stocked sku x warehouse
snaps = []
months = [dt.date(2026, m, 1) for m in range(1, 11)]
def month_end(m): return (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
for p in products:
    for wh in stocking[p[0]]:
        base = rng.randint(300, 1500) * (2 if p[3] == "A" else 1)
        safety = int(base * 0.25); rop = int(base * 0.45)
        for m in months:
            on_hand = int(base * rng.uniform(0.55, 1.25))
            alloc = int(on_hand * rng.uniform(0.05, 0.62))
            if p[7] == "SUP-01" and m.month in (8, 9):
                on_hand = int(base * rng.uniform(0.0, 0.35)); alloc = int(min(on_hand, base*0.2) * rng.uniform(0.7, 1.0))
                if wh == "WH-TOR": alloc = on_hand
            elif rng.random() < 0.03:
                alloc = on_hand
            snaps.append([f"SNP-{len(snaps)+1:05d}", month_end(m), p[0], wh, on_hand, alloc, safety, rop])

# demand forecasts Jan-Nov per stocked sku x warehouse (Nov is open: no actuals yet)
fcs = []
for p in products:
    for wh in stocking[p[0]]:
        lvl = rng.randint(80, 600) * (2 if p[3] == "A" else 1)
        for m in months + [dt.date(2026, 11, 1)]:
            fc = int(lvl * rng.uniform(0.85, 1.2))
            act = None if m.month == 11 else int(fc * rng.uniform(0.72, 1.18))
            fcs.append([f"FC-{len(fcs)+1:05d}", p[0], wh, m, fc, act])

tables = {
 "suppliers": (["supplier_id","supplier_name","supplier_tier","country","category","region","contract_id","payment_terms_days","onboarded_date"], [list(s[:9]) for s in suppliers]),
 "products": (["sku","product_name","category","abc_class","unit_price","unit_cost","lead_time_days","primary_supplier_id","weight_kg"], [list(p) for p in products]),
 "warehouses": (["warehouse_id","warehouse_name","city","region","warehouse_type","capacity_pallets"], [list(w) for w in warehouses]),
 "carriers": (["carrier_id","carrier_name","transport_mode","contracted_otd_target_pct"], [list(c[:4]) for c in carriers]),
 "purchase_orders": (["po_id","order_date","promised_date","received_date","supplier_id","sku","warehouse_id","quantity_ordered","quantity_received","unit_cost","po_status"], pos),
 "shipments": (["shipment_id","po_id","carrier_id","ship_date","delivered_date","quantity_received","damaged_units","freight_cost","shipment_status"], [s[:9] for s in ships]),
 "inventory_snapshots": (["snapshot_id","snapshot_date","sku","warehouse_id","on_hand_units","allocated_units","safety_stock_units","reorder_point_units"], snaps),
 "demand_forecasts": (["forecast_id","sku","warehouse_id","forecast_month","forecast_units","actual_units"], fcs),
 "carrier_performance": (["performance_id","carrier_id","lane","performance_month","shipments","on_time_shipments","damage_claims","avg_transit_days"], perf_rows),
}
for name, (cols, rows) in tables.items():
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in rows: w.writerow([d(v) if isinstance(v, dt.date) else ("" if v is None else v) for v in r])

db = ROOT / "warehouse" / "ostrawind.duckdb"
db.unlink(missing_ok=True)
con = duckdb.connect(str(db))
con.execute("create schema supply_chain")
for name in tables:
    con.execute(f"create table supply_chain.{name} as select * from read_csv_auto('{OUT / (name + '.csv')}', header=true)")
for name in tables:
    print(f"{name:22s} {con.execute(f'select count(*) from supply_chain.{name}').fetchone()[0]:>5} rows")
con.close()
