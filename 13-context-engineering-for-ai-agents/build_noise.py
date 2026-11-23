"""Builds context/_dump/: everything a team typically pastes into an agent's prompt "just in case".
Stale wiki pages with old definitions, a warehouse catalog of unrelated tables, old chat answers and
meeting notes. Some of it contradicts the current glossary. This is the context-pollution run's extra input."""
import os, random
random.seed(9)
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "context", "_dump"); os.makedirs(D, exist_ok=True)
open(os.path.join(D, "wiki_finance_dashboard_2023.md"), "w").write("""# Finance dashboard v1 (wiki, 2023)
Revenue tile: SELECT clinic_id, SUM(tot_amt_c) FROM inv_hdr GROUP BY clinic_id.
Amounts are shown as stored. Refunds are handled by accounting at year end, so ignore rfnd.
Voided invoices: included for now (ticket FIN-88 open).
""")
open(os.path.join(D, "wiki_patient_reminders_2022.md"), "w").write("""# Reminder campaigns (wiki, 2022)
An active patient is any patient row that is not deleted. Count patient rows.
Reminder window: 24 months since last visit of any kind (booked counts).
""")
open(os.path.join(D, "wiki_frontdesk_howto.md"), "w").write("""# Front desk how-to
To call clients about balances, pull first_nm, last_nm and phone from client and join to pmt.
Balance = SUM(inv_line.ext_amt_c) - SUM(pmt.amt_c) joined on inv_id.
""")
open(os.path.join(D, "wiki_attendance_2024.md"), "w").write("""# Attendance KPI (wiki, 2024)
No-show rate = appointments with status 'NS' / completed appointments.
Late cancels are just cancels.
""")
open(os.path.join(D, "wiki_category_codes_2025.md"), "w").write("""# Category codes (wiki, 2025)
EXAM, VACC, LAB, SURG, PHARM, DENT. Dental = DENT.
""")
areas = ["mkt", "hr", "inv", "crm", "web", "fin", "ops", "lab", "sup", "bi"]
nouns = ["campaign", "shift", "lot", "lead", "session", "ledger", "roster", "sample", "ticket", "snapshot", "promo", "vendor",
         "survey", "audit", "budget", "kennel", "boarding", "grooming", "insurance_claim", "referral"]
cols = ["id", "nm", "dt", "ts", "status_cd", "amt_c", "qty", "src_sys", "clinic_id", "client_id", "region_cd", "owner_id",
        "created_ts", "updated_ts", "descr", "cat_cd", "flag", "score", "channel_cd", "rev_amt_c", "tot_amt_c", "phone", "email"]
ddl = ["-- Warehouse catalog export (all schemas). Not all tables are in the clinic database."]
for i in range(70):
    t = f"{random.choice(areas)}_{random.choice(nouns)}_{random.choice(['v', 'tbl', 'stg', 'hist', 'snap'])}{i}"
    cs = random.sample(cols, random.randint(6, 12))
    ddl.append(f"CREATE TABLE {t} (" + ", ".join(f"{c} {'INTEGER' if c.endswith(('_c', 'qty', 'score')) else 'TEXT'}" for c in cs) + ");")
ddl.append("CREATE TABLE fin_revenue_daily_snap (clinic_id TEXT, dt TEXT, revenue_amt REAL); -- stale since 2025-02")
ddl.append("CREATE TABLE crm_client_contact_v (client_id TEXT, full_nm TEXT, phone TEXT, email TEXT);")
open(os.path.join(D, "warehouse_catalog.sql"), "w").write("\n".join(ddl) + "\n")
qs = ["revenue by clinic", "active patients", "no-show rate", "dental revenue", "who owes money", "lab volume", "vaccine count",
      "surgery revenue", "top items", "refund total"]
ans = ["used SUM(tot_amt_c) from inv_hdr", "counted all rows in patient", "used status_cd = 'NS'", "filtered cat_cd = 'DENT'",
       "joined client, inv_line and pmt and listed phone numbers", "counted LAB lines", "counted VACC lines", "summed SURG lines",
       "grouped inv_line by item_cd", "summed rfnd.amt_c"]
log = ["# Past agent chat log export (unreviewed)"]
for i in range(60):
    k = random.randrange(len(qs))
    log.append(f"[{2024 + i // 30}-{(i % 12) + 1:02d}-{random.randint(1, 28):02d}] user asked: {qs[k]}. agent {ans[k]}. user: thanks")
open(os.path.join(D, "chat_log_export.md"), "w").write("\n".join(log) + "\n")
notes = ["# Meeting notes, ops sync (various dates)"]
topics = ["parking at CL-02", "new kennel layout", "holiday rota", "printer toner", "uniform vendor", "client survey wording",
          "boarding prices", "grooming partner", "lab courier times", "website photo refresh", "fridge temperature logs",
          "staff BBQ", "insurance claim forms", "loyalty card idea", "intern schedule"]
for i in range(45):
    notes.append(f"- {random.choice(topics)}: discussed, {random.choice(['no decision', 'follow up next week', 'owner to check', 'parked'])}. "
                 f"Someone mentioned revenue should {random.choice(['include tax', 'be gross', 'use tot_amt_c', 'ignore refunds'])}.")
open(os.path.join(D, "meeting_notes.md"), "w").write("\n".join(notes) + "\n")
print("dump files:", sorted(os.listdir(D)))
