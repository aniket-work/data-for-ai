"""Fictional retail bank "Kestrel Bay Bank": raw CSV exports for the semantic layer series
(Lesson 10 MetricFlow, Lesson 11 WrenAI, Lesson 12 Cube). Deterministic (seed 10). IDs only, no personal data.
Writes data/raw/*.csv. Months: Jan 2025 .. Oct 2026."""
import csv, os, random, datetime as dt, calendar
random.seed(10)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw"); os.makedirs(OUT, exist_ok=True)
def w(name, cols, rows):
    with open(os.path.join(OUT, name + ".csv"), "w", newline="") as f:
        c = csv.writer(f); c.writerow(cols); c.writerows(rows)
    print(f"{name:<18}{len(rows):>8,} rows")

REGIONS = [("ATL", "Atlantic"), ("CEN", "Central"), ("PRA", "Prairies"), ("PAC", "Pacific")]
BRANCHES = [("BR01", "Halifax Waterfront", "Halifax", "ATL"), ("BR02", "Moncton Main", "Moncton", "ATL"),
            ("BR03", "Toronto King West", "Toronto", "CEN"), ("BR04", "Ottawa Glebe", "Ottawa", "CEN"),
            ("BR05", "Montreal Plateau", "Montreal", "CEN"), ("BR06", "Winnipeg Exchange", "Winnipeg", "PRA"),
            ("BR07", "Calgary Beltline", "Calgary", "PRA"), ("BR08", "Saskatoon Riverside", "Saskatoon", "PRA"),
            ("BR09", "Vancouver Gastown", "Vancouver", "PAC"), ("BR10", "Victoria Harbour", "Victoria", "PAC")]
#            id      name                     type      family        annual rate
PRODUCTS = [("CHQ", "Everyday Chequing",       "deposit", "chequing",      0.0010),
            ("SAV", "High-Interest Savings",   "deposit", "savings",       0.0300),
            ("GIC", "1-Year GIC",              "deposit", "term deposit",  0.0425),
            ("MTG", "Fixed Mortgage",          "loan",    "mortgage",      0.0519),
            ("PLN", "Personal Loan",           "loan",    "personal loan", 0.0899),
            ("LOC", "Business Line of Credit", "loan",    "line of credit",0.0795)]
PT = {p[0]: p for p in PRODUCTS}
SEGMENTS = [("Retail", 0.72), ("Premier", 0.16), ("Small Business", 0.12)]
REG_RISK = {"ATL": 1.0, "CEN": 0.8, "PRA": 1.7, "PAC": 1.1}          # Prairies delinquency trends up in 2026
START, END = dt.date(2025, 1, 1), dt.date(2026, 10, 31)
def month_ends():
    d = START
    while d <= END:
        yield dt.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
        d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
MONTHS = list(month_ends())
def rdate(a, b): return a + dt.timedelta(days=random.randrange((b - a).days + 1))

w("regions", ["region_id", "region_name"], REGIONS)
w("branches", ["branch_id", "branch_name", "city", "region_id"], BRANCHES)
w("products", ["product_id", "product_name", "product_type", "product_family", "annual_rate"], PRODUCTS)

customers = []
for i in range(1, 2401):
    seg = random.choices([s for s, _ in SEGMENTS], [p for _, p in SEGMENTS])[0]
    br = random.choices(BRANCHES, [1.0, .6, 1.6, 1.1, 1.2, .8, 1.2, .6, 1.4, .7])[0]
    joined = rdate(dt.date(2019, 1, 1), dt.date(2026, 9, 30)) if random.random() < .8 else rdate(dt.date(2025, 1, 1), dt.date(2026, 10, 25))
    customers.append((f"C{i:05d}", seg, br[0], joined.isoformat()))
w("customers", ["customer_id", "segment", "home_branch_id", "joined_on"], customers)

accounts = []; n = 0
for cid, seg, br, joined in customers:
    jd = dt.date.fromisoformat(joined)
    mix = ({"Retail": ["CHQ", "SAV", "GIC", "MTG", "PLN"], "Premier": ["CHQ", "SAV", "GIC", "GIC", "MTG"],
            "Small Business": ["CHQ", "SAV", "LOC", "LOC", "PLN"]}[seg])
    prods = ["CHQ"] + random.sample(mix[1:], k=random.choice([1, 1, 2, 2, 3]))
    for p in prods:
        n += 1
        opened = jd if p == "CHQ" else rdate(jd, max(jd, END - dt.timedelta(days=3)))
        closed = ""
        if random.random() < .07 and (END - opened).days > 120:
            closed = rdate(opened + dt.timedelta(days=90), END).isoformat()
        principal = ""
        if PT[p][2] == "loan":
            principal = {"MTG": random.randrange(180, 820) * 1000, "PLN": random.randrange(5, 45) * 1000,
                         "LOC": random.randrange(20, 250) * 1000}[p]
            if seg == "Premier": principal = int(principal * 1.4)
        accounts.append([f"A{n:06d}", cid, p, br, opened.isoformat(), closed, principal])
w("accounts", ["account_id", "customer_id", "product_id", "branch_id", "opened_on", "closed_on", "original_principal"], accounts)

reg_of = {b[0]: b[3] for b in BRANCHES}; seg_of = {c[0]: c[1] for c in customers}
bal = []; k = 0
for a in accounts:
    aid, cid, p, br, op, cl, prin = a
    op = dt.date.fromisoformat(op); cl = dt.date.fromisoformat(cl) if cl else None
    ptype, rate = PT[p][2], PT[p][4]
    base = {"CHQ": random.lognormvariate(8.2, .8), "SAV": random.lognormvariate(9.6, .9), "GIC": random.randrange(5, 120) * 1000}[p] if ptype == "deposit" else float(prin)
    if ptype == "deposit": base *= 3.2
    if seg_of[cid] == "Premier" and ptype == "deposit": base *= 2.5
    if seg_of[cid] == "Small Business" and ptype == "deposit": base *= 1.8
    risk = REG_RISK[reg_of[br]] * {"MTG": .35, "PLN": 1.6, "LOC": 1.3}.get(p, 0) * (1.3 if seg_of[cid] == "Small Business" else 1.0)
    dpd = 0; b = base
    for me in MONTHS:
        if me < op or (cl and me >= cl): continue
        age = (me.year - op.year) * 12 + me.month - op.month
        if ptype == "deposit":
            b = max(50.0, b * random.uniform(.97, 1.045)) if p != "GIC" else b
        else:
            term = {"MTG": 300, "PLN": 60, "LOC": 120}[p]
            b = max(0.0, float(prin) * max(0.0, 1 - age / term) * (random.uniform(.75, 1.0) if p == "LOC" else 1.0))
            drift = 1.0 + (0.9 if (reg_of[br] == "PRA" and me.year == 2026) else 0.0)
            if dpd == 0 and random.random() < .012 * risk * drift: dpd = 30
            elif dpd > 0: dpd = dpd + 30 if random.random() < .55 else 0
            dpd = min(dpd, 180)
        if ptype == "loan" and b <= 0: continue
        interest = round(b * rate / 12 * (0 if (ptype == "loan" and dpd >= 90) else 1), 2)  # non-accrual at 90+ dpd
        k += 1
        bal.append((f"B{k:07d}", aid, me.isoformat(), round(b, 2), dpd if ptype == "loan" else 0, interest))
w("monthly_balances", ["balance_id", "account_id", "balance_date", "balance", "days_past_due", "interest_amount"], bal)

tx = []; t = 0
chq = {}
for a in accounts:
    if a[2] in ("CHQ", "LOC"): chq.setdefault(a[1], []).append(a)
for cid, accs in chq.items():
    a = accs[0]; op = dt.date.fromisoformat(a[4]); cl = dt.date.fromisoformat(a[5]) if a[5] else END
    lam = {"Retail": 4, "Premier": 6, "Small Business": 9}[seg_of[cid]]
    dormant_from = rdate(START, END) if random.random() < .18 else None
    for me in MONTHS:
        first = dt.date(me.year, me.month, 1)
        if me < op or first > cl: continue
        if dormant_from and first >= dormant_from: break
        if random.random() < .12: continue            # quiet month
        for _ in range(max(1, int(random.gauss(lam, 2)))):
            d = rdate(max(first, op), min(me, cl))
            t += 1
            ch = random.choices(["mobile", "online", "branch", "atm"], [.55, .2, .1, .15])[0]
            amt = round(random.lognormvariate(4.3, 1.0) * (3 if seg_of[cid] == "Small Business" else 1), 2)
            tx.append((f"T{t:07d}", a[0], cid, d.isoformat(), ch, amt))
tx.sort(key=lambda r: r[3])
w("transactions", ["transaction_id", "account_id", "customer_id", "transaction_date", "channel", "amount"], tx)
