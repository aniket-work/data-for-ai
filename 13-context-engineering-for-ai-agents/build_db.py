"""Builds data/brightpaw.db: a fictional veterinary clinic chain (SQLite, seed 6).
Every clinic, client, pet and number is invented. Phone numbers use the fictional 555-01xx range.
The schema is deliberately "real world": short cryptic names, status codes, amounts in cents,
a renamed category code, a migration that duplicated invoices, and payments that are many-per-invoice."""
import sqlite3, random, os, datetime as dt
random.seed(6)
HERE = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(HERE, "data", "brightpaw.db")
os.makedirs(os.path.dirname(DB), exist_ok=True)
if os.path.exists(DB): os.remove(DB)
con = sqlite3.connect(DB); cur = con.cursor()
cur.executescript("""
CREATE TABLE clinic  (clinic_id TEXT PRIMARY KEY, clinic_nm TEXT, city TEXT, region_cd TEXT, opened_dt TEXT);
CREATE TABLE client  (client_id TEXT PRIMARY KEY, first_nm TEXT, last_nm TEXT, phone TEXT, home_clinic_id TEXT REFERENCES clinic);
CREATE TABLE patient (patient_id TEXT PRIMARY KEY, client_id TEXT REFERENCES client, pet_nm TEXT, species TEXT, birth_dt TEXT, status_cd TEXT);
CREATE TABLE appt    (appt_id TEXT PRIMARY KEY, patient_id TEXT REFERENCES patient, clinic_id TEXT REFERENCES clinic, appt_ts TEXT, status_cd TEXT, svc_line TEXT);
CREATE TABLE item    (item_cd TEXT PRIMARY KEY, item_descr TEXT, cat_cd TEXT);
CREATE TABLE inv_hdr (inv_id TEXT PRIMARY KEY, appt_id TEXT REFERENCES appt, clinic_id TEXT REFERENCES clinic, inv_dt TEXT, status_cd TEXT, tot_amt_c INTEGER, tax_amt_c INTEGER, src_sys TEXT);
CREATE TABLE inv_line(line_id INTEGER PRIMARY KEY, inv_id TEXT REFERENCES inv_hdr, item_cd TEXT REFERENCES item, cat_cd TEXT, qty INTEGER, ext_amt_c INTEGER);
CREATE TABLE pmt     (pmt_id INTEGER PRIMARY KEY, inv_id TEXT REFERENCES inv_hdr, pmt_dt TEXT, amt_c INTEGER, method_cd TEXT);
CREATE TABLE rfnd    (rfnd_id INTEGER PRIMARY KEY, inv_id TEXT REFERENCES inv_hdr, rfnd_dt TEXT, amt_c INTEGER, reason_cd TEXT);
""")
CLINICS = [("CL-01","Brightpaw Westmere","Westmere","W","2019-04-01"),("CL-02","Brightpaw Larch Bay","Larch Bay","W","2020-09-14"),
           ("CL-03","Brightpaw Cedar Hollow","Cedar Hollow","W","2021-03-02"),("CL-04","Brightpaw Eastgate","Eastgate","E","2018-11-20"),
           ("CL-05","Brightpaw Riverbend","Riverbend","E","2022-06-06"),("CL-06","Brightpaw Pinecrest","Pinecrest","E","2023-01-16")]
cur.executemany("INSERT INTO clinic VALUES (?,?,?,?,?)", CLINICS)
FIRST = "Ava Ben Cleo Dev Elin Faye Gus Hana Ivo Jun Kai Lena Milo Nora Omar Pia Quin Rhea Sami Tess Uma Vik Wren Yara Zane".split()
LAST = "Ashdown Birch Calder Dunmore Ellery Fenwick Garrow Hollis Ingram Jessop Kettle Lowry Marlow Northam Orrin Pell Quarry Rook Sallow Thorne".split()
ITEMS = [("EXM-01","Wellness exam","EXAM",6500),("EXM-02","Sick visit exam","EXAM",7800),("VAC-01","Rabies vaccine","VACC",3200),
         ("VAC-02","DHPP vaccine","VACC",3800),("LAB-01","Blood panel","LAB",14500),("LAB-02","Urinalysis","LAB",5200),
         ("SRG-01","Spay / neuter","SURG",42000),("SRG-02","Mass removal","SURG",61000),("RX-01","Flea and tick, 3 mo","PHARM",5900),
         ("RX-02","Antibiotic course","PHARM",3400),("DEN-01","Dental cleaning","DENT",38000),("DEN-02","Tooth extraction","DENT",24000)]
cur.executemany("INSERT INTO item VALUES (?,?,?)", [(c,d,k) for c,d,k,_ in ITEMS])
PRICE = {c: p for c,_,_,p in ITEMS}; CAT = {c: k for c,_,k,_ in ITEMS}
clients = []
for i in range(1, 301):
    cid = f"C-{i:04d}"; home = random.choice(CLINICS)[0]
    clients.append((cid, random.choice(FIRST), random.choice(LAST), f"555-01{random.randint(0,99):02d}", home))
cur.executemany("INSERT INTO client VALUES (?,?,?,?,?)", clients)
PETS = "Biscuit Mochi Pepper Juniper Ziggy Olive Rocket Maple Pickles Nova Basil Tofu Luna Hazel Otis Clover".split()
patients = []
for i in range(1, 421):
    c = clients[(i * 7) % 300]
    st = random.choices(["A", "D", "T"], [0.86, 0.08, 0.06])[0]
    patients.append((f"P-{i:04d}", c[0], random.choice(PETS), random.choice(["dog","dog","cat","cat","rabbit"]),
                     f"{random.randint(2010, 2025)}-{random.randint(1,12):02d}-15", st))
cur.executemany("INSERT INTO patient VALUES (?,?,?,?,?,?)", patients)
home_of = {c[0]: c[4] for c in clients}
# per clinic Q3-2026 status mix: (no-show, late cancel, cancel). CL-02 has the most hard no-shows,
# CL-05 has the most no-shows once late cancels (<24 h) are counted, as the business defines it.
MIX = {"CL-01": (.05,.03,.08), "CL-02": (.09,.01,.07), "CL-03": (.05,.04,.08), "CL-04": (.04,.02,.09), "CL-05": (.06,.07,.06), "CL-06": (.05,.02,.08)}
start = dt.date(2025, 1, 1); end = dt.date(2026, 9, 30)
appts = []; n = 0
# some patients are "lapsed": no visits since early 2025
lapsed = set(random.sample([p[0] for p in patients], 70))
for p in patients:
    k = random.randint(6, 20)
    for _ in range(k):
        d = start + dt.timedelta(days=random.randint(0, (end - start).days))
        if p[0] in lapsed and d > dt.date(2025, 3, 1): continue
        if p[5] != "A" and d > dt.date(2025, 9, 1): continue
        clinic = home_of[p[1]] if random.random() < .85 else random.choice(CLINICS)[0]
        ns, lc, cn = MIX[clinic] if d >= dt.date(2026, 7, 1) else (.05, .03, .08)
        r = random.random()
        st = "NSH" if r < ns else "LCN" if r < ns + lc else "CNL" if r < ns + lc + cn else "CMP"
        n += 1
        appts.append((f"A-{n:05d}", p[0], clinic, f"{d} {random.randint(8,17):02d}:{random.choice(['00','20','40'])}", st,
                      random.choice(["GEN","GEN","GEN","SURG","DENT","EMRG"])))
appts.sort(key=lambda a: a[3])
cur.executemany("INSERT INTO appt VALUES (?,?,?,?,?,?)", appts)
inv_n = 0; line_n = 0; pmt_n = 0; rf_n = 0
hdrs, lines, pmts, rfnds = [], [], [], []
def add_invoice(a, src="vetpos2", dup_of=None):
    global inv_n, line_n, pmt_n, rf_n
    inv_n += 1; iid = f"INV-{inv_n:06d}"; d = a[3][:10]
    if dup_of: chosen = dup_of
    else:
        pool = ["EXM-01","EXM-02","VAC-01","VAC-02","LAB-01","LAB-02","RX-01","RX-02"]
        if a[5] == "SURG": pool += ["SRG-01","SRG-02"] * 3
        if a[5] == "DENT": pool += ["DEN-01","DEN-02"] * 4
        chosen = random.sample(pool, random.randint(1, 3))
        if a[5] == "DENT" and not any(c.startswith("DEN") for c in chosen): chosen.append("DEN-01")
        # dental demand grows after a July promo
        if a[5] == "DENT" and d >= "2026-07-01" and random.random() < .35: chosen.append("DEN-02")
    sub = 0
    for it in chosen:
        line_n += 1; qty = 1
        amt = PRICE[it] * qty; sub += amt
        cat = CAT[it]
        if cat == "DENT" and d >= "2026-07-01": cat = "DNT"   # DEC-14: code renamed when the new POS went live
        lines.append((line_n, iid, it, cat, qty, amt))
    tax = round(sub * .13); st = "V" if (not dup_of and random.random() < .04) else "P"
    hdrs.append((iid, a[0], a[2], d, st, sub + tax, tax, src))
    if st == "P" and not dup_of:
        r = random.random(); total = sub + tax
        if r < .80: parts = [total] if random.random() < .7 else [total // 2, total - total // 2]
        elif r < .975: parts = [total // 3, total // 3, total - 2 * (total // 3)]
        else: parts = [total // 4] if random.random() < .5 else []   # unpaid balance
        for j, amt in enumerate(parts):
            pmt_n += 1; pmts.append((pmt_n, iid, str(dt.date.fromisoformat(d) + dt.timedelta(days=j * 14)), amt, random.choice(["CARD","CARD","DEBIT","CASH"])))
        if random.random() < .03:
            rf_n += 1; rfnds.append((rf_n, iid, str(dt.date.fromisoformat(d) + dt.timedelta(days=5)), round(sub * random.choice([.25,.5,1.0])), random.choice(["SVC","PRICE","DUP"])))
    return chosen
for a in appts:
    if a[4] != "CMP": continue
    ch = add_invoice(a)
    # QRK-07: the August 2026 migration at CL-03 re-imported some invoices from the legacy POS
    if a[2] == "CL-03" and "2026-08-01" <= a[3][:10] <= "2026-08-31" and random.random() < .6:
        add_invoice(a, src="legacy_pos", dup_of=ch)
cur.executemany("INSERT INTO inv_hdr VALUES (?,?,?,?,?,?,?,?)", hdrs)
cur.executemany("INSERT INTO inv_line VALUES (?,?,?,?,?,?)", lines)
cur.executemany("INSERT INTO pmt VALUES (?,?,?,?,?)", pmts)
cur.executemany("INSERT INTO rfnd VALUES (?,?,?,?,?)", rfnds)
con.commit()
for t in ["clinic","client","patient","appt","item","inv_hdr","inv_line","pmt","rfnd"]:
    print(f"{t:9s}", cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
