"""Enforces permissions in code, not just in the prompt.
Opens the database read-only and shadows each table with a TEMP VIEW of the same name:
- row-level access: only the clinics the role may see (POL-ROW-03)
- column-level access: client names and phone numbers are removed (POL-PII-01)
Unqualified table names resolve to the temp views first, so the agent's SQL needs no changes."""
import sqlite3, yaml, os
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "brightpaw.db")

def open_raw():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

def open_guarded(role):
    perms = yaml.safe_load(open(os.path.join(HERE, "context", "permissions.yaml")))["roles"][role]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.execute("PRAGMA temp_store = MEMORY")
    ids = perms["clinics"]
    inlist = "(" + ",".join(f"'{c}'" for c in ids) + ")" if isinstance(ids, list) else None
    w = (lambda col: f" WHERE {col} IN {inlist}") if inlist else (lambda col: "")
    views = {
        "clinic":   f"SELECT * FROM main.clinic{w('clinic_id')}",
        "appt":     f"SELECT * FROM main.appt{w('clinic_id')}",
        "inv_hdr":  f"SELECT * FROM main.inv_hdr{w('clinic_id')}",
        "inv_line": "SELECT * FROM main.inv_line WHERE inv_id IN (SELECT inv_id FROM temp.inv_hdr)",
        "pmt":      "SELECT * FROM main.pmt WHERE inv_id IN (SELECT inv_id FROM temp.inv_hdr)",
        "rfnd":     "SELECT * FROM main.rfnd WHERE inv_id IN (SELECT inv_id FROM temp.inv_hdr)",
        "patient":  "SELECT * FROM main.patient",
        "item":     "SELECT * FROM main.item",
    }
    if not perms["pii"]:
        views["client"] = "SELECT client_id, home_clinic_id FROM main.client"   # names and phone removed
    else:
        views["client"] = "SELECT * FROM main.client"
    for name, sql in views.items():
        con.execute(f"CREATE TEMP VIEW {name} AS {sql}")
    return con

FORBIDDEN = ("main.", "sqlite_", "attach", "pragma", "insert", "update", "delete", "drop", "create", "alter")
def check_sql(sql):
    """Only single read-only SELECT/WITH statements; no reaching around the views."""
    s = sql.strip().rstrip(";").lower()
    if not (s.startswith("select") or s.startswith("with")): return "only SELECT or WITH queries are allowed"
    if ";" in s: return "only one statement is allowed"
    for f in FORBIDDEN:
        if f in s: return f"'{f.strip('.')}' is not allowed"
    return None
