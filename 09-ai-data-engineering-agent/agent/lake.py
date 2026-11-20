"""The tiny lakehouse: raw files (bronze) in lake/raw, curated tables (silver) in a DuckDB file.

Everything the agent can *do* to data lives here as small, typed functions. The model chooses
which ones to call and with which arguments; it never gets a raw database handle.
"""
import json, re, shutil
import duckdb
from . import config

COLUMNS = ["ticket_id", "sold_at", "route", "ticket_type", "fare"]
TS_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M", "%d.%m.%Y %H:%M"]
FIX_KINDS = {
    "dedupe": "keep one row per value of <column> (the business key)",
    "trim_upper": "trim spaces and upper-case a text code column",
    "parse_money": "turn text like '$12.50' or '12.50' into DECIMAL(10,2)",
    "parse_timestamp": "parse mixed date/time text formats into TIMESTAMP",
    "require_value": "reject rows where <column> is empty after cleaning",
    "must_exist_in_routes": "reject rows whose <column> is not a route_code in routes.json",
}
CHECK_KINDS = {
    "expected_columns": "the batch has exactly the columns ticket_id, sold_at, route, ticket_type, fare",
    "not_null": "<column> is never empty",
    "unique": "<column> has no duplicates, inside the batch or against curated.tickets",
    "accepted_values": "<column> values (trimmed, upper-cased) are known: routes.json for route, values already in curated.tickets for other columns",
    "parses": "<column> converts with the cleaning recipe (timestamps, money)",
    "row_count": "the batch row count is within 50%-150% of that office's normal day",
}

def connect(read_only=False):
    config.LAKE.mkdir(exist_ok=True)
    return duckdb.connect(str(config.DB), read_only=read_only)

def cols_of(con, sql):
    cur = con.execute(sql); cols = [d[0] for d in cur.description]; cur.fetchall(); return cols

def q(s): return "'" + str(s).replace("'", "''") + "'"
def shape(col): return (f"regexp_replace(regexp_replace(regexp_replace({col}, '[0-9]', '9', 'g'),"
                        f" '[a-z]', 'a', 'g'), '[A-Z]', 'A', 'g')")

# ------------------------------------------------------------------ discover
def list_sources():
    out = []
    for p in sorted(config.RAW.iterdir()):
        if p.suffix == ".csv":
            header = open(p).readline().strip().split(",")
            n = sum(1 for _ in open(p)) - 1
            out.append(f"{p.name:38s} csv   {n:5d} rows  columns: {', '.join(header)}")
        elif p.suffix == ".json":
            out.append(f"{p.name:38s} json  {len(json.load(open(p))):5d} records")
    return "\n".join(out)

def profile_source(name):
    p = config.RAW / name
    if not p.exists():
        raise ValueError(f"no source named {name!r}; call list_sources first")
    con = duckdb.connect()
    if p.suffix == ".json":
        rel = f"read_json_auto({q(p)})"
    else:
        rel = f"read_csv({q(p)}, all_varchar=true, header=true)"
    cols = cols_of(con, f"SELECT * FROM {rel} LIMIT 0")
    n = con.execute(f"SELECT count(*) FROM {rel}").fetchall()[0][0]
    lines = [f"{name}: {n} rows, {len(cols)} columns"]
    full_dupes = con.execute(f"SELECT count(*) - count(DISTINCT ({', '.join(cols)})) FROM {rel}").fetchall()[0][0]
    key = cols[0]
    key_dupes = con.execute(f"SELECT count(*) - count(DISTINCT {key}) FROM {rel}").fetchall()[0][0]
    lines.append(f"duplicate rows: {full_dupes}   duplicate {key}: {key_dupes}")
    alerts = []
    if full_dupes: alerts.append(f"{full_dupes} fully duplicated rows ({key_dupes} repeated {key})")
    for c in cols:
        v = f"CAST({c} AS VARCHAR)"
        blanks, distinct = con.execute(f"SELECT count(*) FILTER (WHERE {v} IS NULL OR trim({v}) = ''), count(DISTINCT {v}) FROM {rel}").fetchall()[0]
        shapes = con.execute(f"SELECT {shape(v)} s, count(*) n FROM {rel} WHERE {v} IS NOT NULL AND trim({v}) <> '' "
                         f"GROUP BY s ORDER BY n DESC LIMIT 3").fetchall()
        top = con.execute(f"SELECT {v} x, count(*) n FROM {rel} GROUP BY x ORDER BY n DESC, x LIMIT 4").fetchall()
        sh = "; ".join(f"'{s}' x{k}" for s, k in shapes)
        tp = ", ".join(repr(x) for x, _ in top)
        lines.append(f"- {c}: blanks {blanks}, distinct {distinct}, shapes {sh}, top values {tp}")
        if blanks: alerts.append(f"{c}: {blanks} blank values")
        if c == "route" and p.suffix == ".csv":
            ref = [r["route_code"] for r in json.load(open(config.RAW / "routes.json"))]
            bad = con.execute(f"SELECT {c}, count(*) FROM {rel} WHERE {c} NOT IN ({', '.join(map(q, ref))}) GROUP BY 1 ORDER BY 2 DESC").fetchall()
            if bad: alerts.append(f"{c}: values not in routes.json as written: " + ", ".join(f"{v!r} x{n}" for v, n in bad))
    lines.append("ALERTS: " + ("; ".join(alerts) if alerts else "none"))
    return "\n".join(lines)

def compare_grid():
    files = sorted(config.RAW.glob("tickets_*.csv"))
    con = duckdb.connect(); grid = {}
    for p in files:
        rel = f"read_csv({q(p)}, all_varchar=true, header=true)"
        for c in cols_of(con, f"SELECT * FROM {rel} LIMIT 0"):
            sh = con.execute(f"SELECT {shape(c)} s FROM {rel} WHERE {c} IS NOT NULL AND trim({c}) <> '' GROUP BY s ORDER BY count(*) DESC LIMIT 2").fetchall()
            grid.setdefault(c, {})[p.name.split("_")[1]] = [s for (s,) in sh]
    offices = [p.name.split("_")[1] for p in files]
    rows = []
    for c, row in grid.items():
        main = [row.get(o, ["(missing)"])[0] for o in offices]          # compare the main shape of each file
        common = max(sorted(set(main)), key=main.count)
        odd = [o for o, v in zip(offices, main) if v != common]
        rows.append((c, [row.get(o, ["(missing)"]) for o in offices], common, odd))
    return offices, rows

def compare_files():
    """Side by side: the value shapes of each column in every ticket file."""
    offices, rows = compare_grid()
    out = [f"{'column':12s}" + "".join(f"{o:23s}" for o in offices) + "verdict"]
    for c, vals, common, odd in rows:
        verdict = "same format" if not odd else "DIFFERS: " + ", ".join(f"{o} '{vals[offices.index(o)][0]}'" for o in odd) + f" vs others '{common}'"
        out.append(f"{c:12s}" + "".join(f"{' / '.join(repr(x) for x in v)[:22]:23s}" for v in vals) + verdict)
    out.append("Shapes: 9 = digit, A = upper-case letter, a = lower-case letter. A leading space is part of the shape.")
    return "\n".join(out)

def expected_findings():
    """(file, column) pairs that profile_source flagged as ALERTS or compare_files flagged as DIFFERS."""
    out = set()
    _, rows = compare_grid()
    for c, _, _, odd in rows:
        for o in odd: out.add((f"tickets_{o}_2026-10.csv", c))
    for p in sorted(config.RAW.glob("tickets_*.csv")):
        al = profile_source(p.name).splitlines()[-1]
        if "duplicated rows" in al: out.add((p.name, "ticket_id"))
        for col in COLUMNS:
            if f"{col}: " in al: out.add((p.name, col))
    return out

# ------------------------------------------------------------------ clean (recipe -> SQL)
def compile_recipe(fixes):
    """Turn a list of typed fixes into one CREATE TABLE statement (plus a rejects table)."""
    expr = {c: c for c in COLUMNS}
    dedupe_key, rejects = None, []
    for f in fixes:
        k, c = f["kind"], f.get("column")
        if k not in FIX_KINDS:
            raise ValueError(f"unknown fix kind {k!r}; allowed: {', '.join(FIX_KINDS)}")
        if c not in COLUMNS:
            raise ValueError(f"unknown column {c!r}; columns are {', '.join(COLUMNS)}")
        if k == "trim_upper":
            expr[c] = f"upper(trim({expr[c]}))"
        elif k == "parse_money":
            expr[c] = f"TRY_CAST(replace(trim({expr[c]}), '$', '') AS DECIMAL(10,2))"
        elif k == "parse_timestamp":
            expr[c] = "COALESCE(" + ", ".join(f"TRY_STRPTIME(trim({expr[c]}), {q(fm)})" for fm in TS_FORMATS) + ")"
        elif k == "dedupe":
            dedupe_key = c
        elif k == "require_value":
            rejects.append((f"{c} IS NULL", f"{c} missing"))
        elif k == "must_exist_in_routes":
            rejects.append((f"{c} NOT IN (SELECT route_code FROM curated.routes)", f"unknown {c}"))
    files = q(str(config.RAW / "tickets_*.csv"))
    sel = ",\n         ".join(f"{expr[c]} AS {c}" for c in COLUMNS)
    dedupe = (f"\n  QUALIFY row_number() OVER (PARTITION BY {dedupe_key} ORDER BY source_file) = 1" if dedupe_key else "")
    reason = ("CASE " + " ".join(f"WHEN {cond} THEN {q(r)}" for cond, r in rejects) + " END") if rejects else "NULL"
    sql = (f"CREATE OR REPLACE TABLE curated.stage_tickets AS\n"
           f"WITH src AS (\n  SELECT *, parse_filename(filename) AS source_file\n"
           f"  FROM read_csv({files}, all_varchar=true, union_by_name=true, filename=true)\n),\n"
           f"typed AS (\n  SELECT {sel},\n         source_file\n  FROM src{dedupe}\n)\n"
           f"SELECT *, {reason} AS reject_reason FROM typed;\n"
           f"CREATE OR REPLACE TABLE curated.tickets AS SELECT * EXCLUDE (reject_reason) FROM curated.stage_tickets WHERE reject_reason IS NULL;\n"
           f"CREATE OR REPLACE TABLE curated.tickets_rejected AS SELECT * FROM curated.stage_tickets WHERE reject_reason IS NOT NULL;\n"
           f"DROP TABLE curated.stage_tickets;")
    return sql, expr

def load_routes(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS curated")
    con.execute(f"CREATE OR REPLACE TABLE curated.routes AS SELECT * FROM read_json_auto({q(config.RAW / 'routes.json')})")

def preview_recipe(fixes):
    """Dry run in memory: what would the curated table look like?"""
    sql, _ = compile_recipe(fixes)
    con = duckdb.connect()
    load_routes(con); con.execute(sql)
    raw = con.execute(f"SELECT count(*) FROM read_csv({q(str(config.RAW / 'tickets_*.csv'))}, all_varchar=true, union_by_name=true)").fetchall()[0][0]
    ok = con.execute("SELECT count(*) FROM curated.tickets").fetchall()[0][0]
    rej = con.execute("SELECT reject_reason, count(*) FROM curated.tickets_rejected GROUP BY 1 ORDER BY 2 DESC").fetchall()
    return sql, raw, ok, rej

def apply_recipe(fixes):
    sql, _ = compile_recipe(fixes)
    con = connect(); load_routes(con); con.execute(sql)
    out = con.execute("SELECT count(*), min(sold_at), max(sold_at), count(DISTINCT route), count(DISTINCT ticket_type) FROM curated.tickets").fetchall()[0]
    con.close()
    config.STATE.mkdir(exist_ok=True)
    (config.STATE / "recipe.json").write_text(json.dumps(fixes, indent=2))
    (config.STATE / "recipe.sql").write_text(sql + "\n")
    return out

def describe_tables():
    con = connect(read_only=True); out = []
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='curated' ORDER BY 1").fetchall():
        cols = con.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='curated' AND table_name={q(t)} ORDER BY ordinal_position").fetchall()
        n = con.execute(f"SELECT count(*) FROM curated.{t}").fetchall()[0][0]
        out.append(f"curated.{t} ({n} rows): " + ", ".join(f"{c} {d}" for c, d in cols))
        if t == "routes":
            out.append("    rows: " + "; ".join(f"{a} = {b}" for a, b in con.execute("SELECT route_code, name FROM curated.routes ORDER BY 1").fetchall()))
            continue
        for c, d in cols:                                  # low-cardinality text columns: show the exact values
            if d == "VARCHAR" and c not in ("ticket_id", "source_file"):
                vals = con.execute(f"SELECT DISTINCT {c} FROM curated.{t} ORDER BY 1 LIMIT 11").fetchall()
                if len(vals) <= 10: out.append(f"    {c} values: " + ", ".join(repr(v) for (v,) in vals))
    con.close()
    return "\n".join(out)

# ------------------------------------------------------------------ monitor (data contract on incoming batches)
def load_checks():
    p = config.STATE / "checks.json"
    return json.loads(p.read_text()) if p.exists() else []

def run_checks(batch_name):
    p = config.INCOMING / batch_name
    if not p.exists():
        raise ValueError(f"no incoming batch {batch_name!r}")
    checks = load_checks()
    if not checks:
        raise ValueError("no saved checks; run the 'checks' stage first")
    fixes = json.loads((config.STATE / "recipe.json").read_text())
    _, expr = compile_recipe(fixes)
    con = connect(read_only=True)
    rel = f"read_csv({q(p)}, all_varchar=true, header=true)"
    cols = cols_of(con, f"SELECT * FROM {rel} LIMIT 0")
    n = con.execute(f"SELECT count(*) FROM {rel}").fetchall()[0][0]
    res = []
    for i, ch in enumerate(checks, 1):
        k, c = ch["kind"], ch.get("column")
        cid = f"C{i}"
        if k == "expected_columns":
            missing = [x for x in COLUMNS if x not in cols]; extra = [x for x in cols if x not in COLUMNS]
            ok = not missing and not extra
            res.append((cid, k, "-", ok, "ok" if ok else f"missing {missing}, unexpected {extra}"))
            continue
        if k == "row_count":
            prefix = con.execute(f"SELECT split_part(min(ticket_id), '-', 1) FROM {rel}").fetchall()[0][0]   # HF, CP, GI = office
            avg = con.execute(f"SELECT avg(c) FROM (SELECT count(*) c FROM curated.tickets WHERE ticket_id LIKE {q(str(prefix) + '-%')} GROUP BY sold_at::DATE)").fetchall()[0][0] or 0
            ok = 0.5 * avg <= n <= 1.5 * avg
            res.append((cid, k, "-", ok, f"{n} rows vs normal ~{avg:.0f}"))
            continue
        if c not in cols:
            res.append((cid, k, c, False, f"column {c} is missing from the batch")); continue
        if k == "not_null":
            bad = con.execute(f"SELECT count(*) FROM {rel} WHERE {c} IS NULL OR trim({c}) = ''").fetchall()[0][0]
        elif k == "unique":
            bad = con.execute(f"SELECT (SELECT count(*) - count(DISTINCT {c}) FROM {rel}) + "
                          f"(SELECT count(*) FROM {rel} b WHERE b.{c} IN (SELECT {c} FROM curated.tickets))").fetchall()[0][0]
        elif k == "accepted_values":
            bad = con.execute(f"SELECT count(*) FROM {rel} WHERE upper(trim({c})) NOT IN ({known(c)})").fetchall()[0][0]
        elif k == "parses":
            bad = con.execute(f"SELECT count(*) FROM {rel} WHERE {c} IS NOT NULL AND trim({c}) <> '' AND ({expr[c]}) IS NULL").fetchall()[0][0]
        else:
            raise ValueError(f"unknown check kind {k}")
        res.append((cid, k, c, bad == 0, "ok" if bad == 0 else f"{bad} of {n} rows fail"))
    con.close()
    return res, cols, n

def known(c):
    return "SELECT route_code FROM curated.routes" if c == "route" else f"SELECT DISTINCT CAST({c} AS VARCHAR) FROM curated.tickets"

def failing_rows(batch_name, check_id, limit=5):
    checks = load_checks(); i = int(check_id.lstrip("Cc")) - 1
    ch = checks[i]; c = ch.get("column")
    p = config.INCOMING / batch_name
    con = connect(read_only=True)
    rel = f"read_csv({q(p)}, all_varchar=true, header=true)"
    cols = cols_of(con, f"SELECT * FROM {rel} LIMIT 0")
    if ch["kind"] == "accepted_values" and c in cols:
        rows = con.execute(f"SELECT {c}, count(*) n FROM {rel} WHERE upper(trim({c})) NOT IN ({known(c)}) GROUP BY 1 ORDER BY 2 DESC LIMIT {limit}").fetchall()
        return f"unknown {c} values: " + ", ".join(f"{v!r} x{n}" for v, n in rows)
    head = con.execute(f"SELECT * FROM {rel} LIMIT 3").fetchall()
    return f"batch columns: {cols}\nfirst rows: " + "\n".join(map(str, head))

def move_batch(batch_name, to):
    src = config.INCOMING / batch_name
    dst_dir = config.QUARANTINE if to == "quarantine" else config.RAW
    dst_dir.mkdir(exist_ok=True); shutil.move(str(src), str(dst_dir / batch_name))
    return dst_dir / batch_name
