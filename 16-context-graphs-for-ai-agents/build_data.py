"""Build the sample data for a fictional vaccine and biologics cold-chain distributor, "Kestrel Cold Chain".

Writes plain tables to data/ (one CSV per node type, one CSV of edges), the same shape you would land in a
lakehouse before modelling a graph, plus docs_corpus/ (the same facts written as wiki pages and memos, which is
what a plain RAG pipeline would index). Everything is invented; people are role IDs only.
"""
import csv, os, random, json
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "data"); DOCS = os.path.join(HERE, "docs_corpus")
os.makedirs(D, exist_ok=True); os.makedirs(DOCS, exist_ok=True)
rnd = random.Random(16)
TODAY = "2026-10-15"

products = [
    dict(id="PRD-A", name="Vaccine A (multi-dose vial)", range="2-8 C", freeze_sensitive="yes"),
    dict(id="PRD-B", name="Insulin pen B", range="2-8 C", freeze_sensitive="yes"),
    dict(id="PRD-C", name="Biologic C (prefilled syringe)", range="2-8 C", freeze_sensitive="yes"),
]
sites = [dict(id="DC-HFX", kind="distribution centre", city="Halifax"), dict(id="DC-MTL", kind="distribution centre", city="Montreal")] + \
        [dict(id=f"CL-{i:02d}", kind="clinic", city=c) for i, c in enumerate(["Moncton", "Saint John", "Fredericton", "Charlottetown", "Quebec City", "Sherbrooke", "Trois-Rivieres", "Laval"], 1)]
carriers = [dict(id="CR-1", name="Bluefin Courier"), dict(id="CR-2", name="RouteNorth Logistics"), dict(id="CR-3", name="Frostline Express")]
roles = [dict(id="QA-07", role="QA lead"), dict(id="QA-11", role="QA specialist"), dict(id="QA-02", role="QA specialist"), dict(id="AGENT-1", role="release agent (AI)")]
# lots and their stability budgets (minutes a lot may spend outside 2-8 C over its life, from the stability study)
lots = []
for p, n, budget in [("PRD-A", 8, 100), ("PRD-B", 4, 90), ("PRD-C", 4, 60)]:
    for i in range(1, n + 1):
        lots.append(dict(id=f"L-{p[-1]}-{i:02d}", product=p, stability_budget_min=budget, expiry=f"2027-{rnd.randint(3, 12):02d}-28"))

# historical shipments (no excursion) to give the graph realistic bulk
ships, excs = [], []
def ship(sid, lot, dst, carrier, date, src=None):
    p = next(l for l in lots if l["id"] == lot)["product"]
    s = dict(id=sid, lot=lot, product=p, origin=src or ("DC-HFX" if dst in ("CL-01", "CL-02", "CL-03", "CL-04") else "DC-MTL"), destination=dst, carrier=carrier, ship_date=date)
    ships.append(s); return s
sid = 1900
for k in range(48):
    lot = rnd.choice(lots)["id"]; sid += rnd.randint(1, 3)
    m = rnd.randint(1, 9); ship(f"SH-{sid}", lot, rnd.choice([s["id"] for s in sites if s["kind"] == "clinic"]), rnd.choice(["CR-1", "CR-2", "CR-3"]), f"2026-{m:02d}-{rnd.randint(1, 28):02d}")
ships = [s for s in ships if s["id"] not in ("SH-1975", "SH-1990", "SH-2031", "SH-1958", "SH-2040", "SH-2044", "SH-2048")]

def exc(eid, where, lot, date, max_c, min_c, minutes, shipment=None):
    e = dict(id=eid, shipment=shipment or "", site=where, lot=lot, date=date, max_c=max_c, min_c=min_c, minutes=minutes); excs.append(e); return e

# ---- planted history: the decisions that make this a CONTEXT graph
ship("SH-1958", "L-A-01", "CL-05", "CR-2", "2026-02-11")
exc("EXC-1958", "in transit", "L-A-01", "2026-02-11", 9.2, 4.1, 11, "SH-1958")
ship("SH-1975", "L-A-02", "CL-02", "CR-1", "2026-06-10")
exc("EXC-1975", "in transit", "L-A-02", "2026-06-10", 9.9, 4.4, 18, "SH-1975")
ship("SH-1990", "L-C-01", "CL-06", "CR-2", "2026-05-02")
exc("EXC-1990", "in transit", "L-C-01", "2026-05-02", 5.0, -0.8, 5, "SH-1990")
exc("EXC-W0703", "DC-HFX cold room 2", "L-A-04", "2026-07-03", 9.0, 4.8, 40)
ship("SH-2031", "L-A-04", "CL-03", "CR-1", "2026-09-12")
exc("EXC-2031", "in transit", "L-A-04", "2026-09-12", 9.4, 4.6, 25, "SH-2031")
for s, lot, d, mx, mins in [("SH-2040", "L-B-02", "2026-09-08", 9.1, 12), ("SH-2044", "L-A-06", "2026-09-19", 10.4, 21), ("SH-2048", "L-B-03", "2026-09-27", 9.8, 16)]:
    ship(s, lot, "CL-07", "CR-3", d); exc(f"EXC-{s[3:]}", "in transit", lot, d, mx, 4.2, mins, s)
ship("SH-2016", "L-A-07", "CL-08", "CR-2", "2026-08-21")
exc("EXC-2016", "in transit", "L-A-07", "2026-08-21", 8.9, 4.5, 5, "SH-2016")

# ---- today's open cases (the questions)
ship("SH-2051", "L-A-07", "CL-04", "CR-1", "2026-10-14"); exc("EXC-2051", "in transit", "L-A-07", "2026-10-14", 9.6, 4.3, 14, "SH-2051")
ship("SH-2057", "L-C-03", "CL-06", "CR-2", "2026-10-14"); exc("EXC-2057", "in transit", "L-C-03", "2026-10-14", 5.2, -0.5, 6, "SH-2057")
ship("SH-2060", "L-A-04", "CL-01", "CR-1", "2026-10-15"); exc("EXC-2060", "in transit", "L-A-04", "2026-10-15", 10.1, 4.9, 22, "SH-2060")
ship("SH-2063", "L-B-01", "CL-07", "CR-3", "2026-10-15"); exc("EXC-2063", "in transit", "L-B-01", "2026-10-15", 8.4, 4.4, 8, "SH-2063")

policies = [
    dict(id="SOP-TEMP-v2", title="Temperature excursion SOP, version 2", effective_from="2025-01-01", effective_to="2026-03-31",
         rule="Any reading above 8.0 C or below 2.0 C: QUARANTINE the shipment; QA destroys it. No release is allowed."),
    dict(id="SOP-TEMP-v3", title="Temperature excursion SOP, version 3", effective_from="2026-04-01", effective_to="",
         rule=("Apply in order. Step 1: freeze-sensitive product with any reading at or below 0.0 C -> DESTROY, no exceptions. "
               "Step 2: max at most 12.0 C AND at most 30 min AND the lot has at least 60 min of stability budget left before this excursion -> RELEASE "
               "(deduct the minutes from the lot budget). Step 3: anything else -> QUARANTINE pending QA review.")),
    dict(id="POL-SIGNOFF-01", title="Release sign-off", effective_from="2025-01-01", effective_to="",
         rule="An AI agent may propose a disposition. A human QA reviewer approves it before stock moves."),
]
# decisions = the decision traces (trigger, context used, proposal, resolution, approver, outcome)
decisions = [
    dict(id="DEC-097", date="2026-02-11", about="SH-1958", trigger="EXC-1958", policy="SOP-TEMP-v2", disposition="QUARANTINE", proposed_by="QA-02", approved_by="QA-07",
         rationale="11 min at 9.2 C. Version 2 allows no release.", status="final", deducts=0),
    dict(id="DEC-118", date="2026-05-02", about="SH-1990", trigger="EXC-1990", policy="SOP-TEMP-v3", disposition="RELEASE", proposed_by="QA-11", approved_by="QA-11",
         rationale="Dip to -0.8 C lasted only 5 min; judged acceptable because it was short. Exception granted without QA lead.", status="overturned", deducts=5),
    dict(id="DEC-121", date="2026-05-20", about="L-C-01", trigger="OUT-119", policy="SOP-TEMP-v3", disposition="RECALL", proposed_by="QA-07", approved_by="QA-07",
         rationale="Overturns DEC-118. Freeze-sensitive product that froze must be destroyed under v3, regardless of duration. Lot L-C-01 recalled from CL-06.", status="final", deducts=0),
    dict(id="DEC-131", date="2026-06-10", about="SH-1975", trigger="EXC-1975", policy="SOP-TEMP-v3", disposition="RELEASE", proposed_by="QA-02", approved_by="QA-07",
         rationale="18 min, max 9.9 C, lot L-A-02 had 100 min of budget left. Meets v3 release criteria. Stability report STAB-A reviewed.", status="final", deducts=18),
    dict(id="DEC-135", date="2026-07-03", about="L-A-04", trigger="EXC-W0703", policy="SOP-TEMP-v3", disposition="RELEASE", proposed_by="QA-02", approved_by="QA-07",
         rationale="Cold room 2 door alarm, 40 min at 9.0 C. Stock kept in date. QA lead accepted the deviation and deducted 40 min.", status="final", deducts=40),
    dict(id="DEC-138", date="2026-08-21", about="SH-2016", trigger="EXC-2016", policy="SOP-TEMP-v3", disposition="RELEASE", proposed_by="QA-11", approved_by="QA-07",
         rationale="5 min at 8.9 C, lot L-A-07 had 100 min left.", status="final", deducts=5),
    dict(id="DEC-140", date="2026-09-30", about="CR-3", trigger="EXC-2048", policy="POL-SIGNOFF-01", disposition="CARRIER PROBATION", proposed_by="QA-07", approved_by="QA-07",
         rationale="Third Frostline excursion in 30 days (EXC-2040, EXC-2044, EXC-2048). Until 2026-12-31 every Frostline shipment with an excursion is ESCALATED to the QA lead, even if v3 would release it.", status="final", deducts=0, valid_to="2026-12-31"),
    dict(id="DEC-142", date="2026-09-12", about="SH-2031", trigger="EXC-2031", policy="SOP-TEMP-v3", disposition="RELEASE", proposed_by="AGENT-1", approved_by="QA-07",
         rationale="25 min at 9.4 C, lot L-A-04 had 60 min left (100 minus 40). Released; 35 min remain.", status="final", deducts=25),
]
for d, s, mx, mins, lot in [("DEC-139", "SH-2040", 9.1, 12, "L-B-02"), ("DEC-141", "SH-2044", 10.4, 21, "L-A-06"), ("DEC-143", "SH-2048", 9.8, 16, "L-B-03")]:
    decisions.append(dict(id=d, date=next(x["ship_date"] for x in ships if x["id"] == s), about=s, trigger=f"EXC-{s[3:]}", policy="SOP-TEMP-v3", disposition="RELEASE",
                          proposed_by="QA-11", approved_by="QA-07", rationale=f"{mins} min, max {mx} C, budget OK.", status="final", deducts=mins))
outcomes = [
    dict(id="OUT-119", date="2026-05-16", decision="DEC-118", result="Clinic CL-06 reported visible particles in two syringes; retest failed.", kind="adverse"),
    dict(id="OUT-132", date="2026-08-10", decision="DEC-131", result="Potency retest passed; no complaints after 60 days.", kind="good"),
    dict(id="OUT-136", date="2026-09-01", decision="DEC-135", result="No complaints; stock used before expiry.", kind="good"),
]
docs_ref = [dict(id="STAB-A", title="Stability study, Vaccine A", note="Lots tolerate up to 100 cumulative minutes at 8-12 C over shelf life.")]

def w(name, rows):
    with open(os.path.join(D, name), "w", newline="") as f:
        cw = csv.DictWriter(f, fieldnames=list(rows[0].keys())); cw.writeheader(); cw.writerows(rows)
w("products.csv", products); w("sites.csv", sites); w("carriers.csv", carriers); w("roles.csv", roles); w("lots.csv", lots)
w("shipments.csv", sorted({s["id"]: s for s in ships}.values(), key=lambda s: s["id"])); w("excursions.csv", excs); w("policies.csv", policies)
w("decisions.csv", [{**d, "valid_to": d.get("valid_to", "")} for d in decisions]); w("outcomes.csv", outcomes); w("documents.csv", docs_ref)

# ---- the same knowledge as unstructured text (what a plain RAG index sees)
def doc(name, text): open(os.path.join(DOCS, name), "w").write(text.strip() + "\n")
for p in policies:
    doc(f"{p['id'].lower()}.md", f"# {p['title']}\n\n{p['rule']}\n\nOwner: Quality Assurance.")
for d in decisions:
    doc(f"memo_{d['id'].lower()}.md", f"# Decision memo {d['id']} ({d['date']})\n\nSubject: {d['about']}. Disposition: {d['disposition']}.\n\n{d['rationale']}")
for o in outcomes:
    doc(f"followup_{o['id'].lower()}.md", f"# Follow-up {o['id']} ({o['date']})\n\n{o['result']}")
doc("stab-a.md", "# Stability study, Vaccine A\n\n" + docs_ref[0]["note"])
doc("wiki_cold_chain_faq.md", """# Cold chain FAQ (team wiki)

Excursions above 8 C mean the shipment is quarantined. Short dips are usually fine.
Ask QA if unsure. Frostline is our cheapest carrier.""")
print(f"products {len(products)}, lots {len(lots)}, shipments {len({s['id'] for s in ships})}, excursions {len(excs)}, decisions {len(decisions)}, outcomes {len(outcomes)}, docs {len(os.listdir(DOCS))}")
