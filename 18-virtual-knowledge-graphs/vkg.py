"""Lesson 18: a Virtual Knowledge Graph over Alder & Finch Outdoor's live PostgreSQL tables (Ontop + SPARQL),
compared with the classic ETL copy into a triple store (Ontop materialize + Oxigraph).

  python vkg.py up                     start the Ontop SPARQL endpoint (dev mode) and time the first answer
  python vkg.py tables                 the legacy tables the business actually runs on
  python vkg.py mapping                a few lines of the ontology and the mapping
  python vkg.py ask q2 [--sql]         SPARQL against the virtual graph (Ontop endpoint), optionally the SQL it became
  python vkg.py etl                    the "before": copy everything into a triple store
  python vkg.py compare                the same four questions on both, answers and timings
  python vkg.py live                   the service desk changes data; who sees it?
  python vkg.py schema-change          a DBA renames a column; fix the mapping; what does each side cost?
  python vkg.py scorecard              all measured numbers in one table
  python vkg.py fabric                 how the same mapping points at a Microsoft Fabric SQL endpoint
  python vkg.py reset                  rebuild the data, restore the mapping, drop the copy
Needs: PostgreSQL with db/build_data.py loaded, and an Ontop endpoint (see README) on ENDPOINT.
"""
import os, sys, json, time, re, shutil, subprocess, statistics, datetime as dt
import requests, psycopg
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel
from rich import box

os.environ.setdefault("TERM", "xterm-256color")
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
DSN = os.environ.get("VKG_DSN", "postgresql://vkg@127.0.0.1:5432/alderfinch")
ENDPOINT = os.environ.get("VKG_ENDPOINT", "http://127.0.0.1:8090")
ONTOP = os.environ.get("ONTOP_CLI", "ontop")
ONT, MAP, PROPS = "vkg/alderfinch.ttl", "vkg/alderfinch.obda", "vkg/alderfinch.properties"
COPY_DIR = "copy"; RUNS = "runs"; os.makedirs(RUNS, exist_ok=True)
QUERIES = {"q1": "sparql/q1_tents.rq", "q2": "sparql/q2_open_tent_claims.rq", "q3": "sparql/q3_products_by_class.rq",
           "q4": "sparql/q4_claims_by_issue.rq", "q5": "sparql/q5_new_claims.rq"}
LABEL = {"q1": "Every tent and its supplier", "q2": "Tent claims open > 14 days, by supplier", "q3": "How many products? (subclasses)",
         "q4": "Open claims by product type", "q5": "New claims since the Nov 20 snapshot"}
con = Console(width=int(os.environ.get("VKG_WIDTH", "132")), highlight=False)

def save(name, data): json.dump(data, open(f"{RUNS}/{name}.json", "w"), indent=1, default=str)
def load(name):
    p = f"{RUNS}/{name}.json"; return json.load(open(p)) if os.path.exists(p) else None
def q(name): return open(QUERIES[name]).read()
def fmt_mb(b): return f"{b/1e6:,.1f} MB"
def dir_size(p): return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)

def vkg_select(text):
    r = requests.post(f"{ENDPOINT}/sparql", data={"query": text}, headers={"Accept": "application/sparql-results+json"}, timeout=120)
    if r.status_code != 200: raise RuntimeError(r.text.strip().splitlines()[0][:300] if r.text.strip() else f"HTTP {r.status_code}")
    js = r.json(); cols = js["head"]["vars"]
    return cols, [[b.get(c, {}).get("value", "") for c in cols] for b in js["results"]["bindings"]]
def vkg_sql(text):
    r = requests.post(f"{ENDPOINT}/ontop/reformulate", data={"query": text}, timeout=60); r.raise_for_status()
    t = r.text; i = t.find("SELECT"); return t[i:].strip() if i >= 0 else t.strip()
def copy_store():
    import pyoxigraph as ox
    return ox.Store(COPY_DIR)
def copy_select(store, text):
    res = store.query(text); cols = [v.value for v in res.variables]
    return cols, [[(x.value if x is not None else "") for x in row] for row in res]
def timed(fn, *a, n=5):
    ts = []; out = None
    for _ in range(n):
        t0 = time.perf_counter(); out = fn(*a); ts.append((time.perf_counter() - t0) * 1000)
    return out, statistics.median(ts)
def wait_endpoint(timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if requests.post(f"{ENDPOINT}/sparql", data={"query": "ASK {}"}, timeout=3).status_code == 200: return time.time() - t0
        except requests.RequestException: pass
        time.sleep(0.25)
    raise RuntimeError("endpoint not up")
def show_rows(cols, rows, title, limit=12, style="cyan"):
    t = Table(title=title, box=box.SIMPLE_HEAVY, title_style=f"bold {style}", header_style="bold", min_width=72, title_justify="left")
    for c in cols: t.add_column(c, justify="right" if rows and re.fullmatch(r"[\d.]+", rows[0][cols.index(c)] or "x") else "left")
    for r in rows[:limit]: t.add_row(*r)
    if len(rows) > limit: t.add_row(*([f"... {len(rows)-limit} more"] + [""] * (len(cols) - 1)))
    con.print(t)

# ---------------------------------------------------------------- commands
def cmd_tables():
    t = Table(title="Alder & Finch Outdoor: three legacy systems, one PostgreSQL (fictional data)", box=box.SIMPLE_HEAVY, title_style="bold cyan")
    for c in ("table", "rows", "columns (as the DBAs named them)"): t.add_column(c, justify="right" if c == "rows" else "left")
    with psycopg.connect(DSN) as c:
        for s, tb in [("crm", "cst_mstr"), ("erp", "sup_mstr"), ("erp", "prd_mstr"), ("erp", "ord_hdr"), ("erp", "ord_ln"), ("svc", "wrty_tkt")]:
            n = c.execute(f"SELECT count(*) FROM {s}.{tb}").fetchone()[0]
            cols = [r[0] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (s, tb))]
            t.add_row(f"{s}.{tb}", f"{n:,}", ", ".join(cols))
        size = c.execute("SELECT sum(pg_total_relation_size(c.oid)) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('crm','erp','svc') AND c.relkind='r'").fetchone()[0]
        codes = c.execute("SELECT string_agg(DISTINCT cat_cd, ', ') FROM erp.prd_mstr").fetchone()[0]
        sts = c.execute("SELECT string_agg(DISTINCT sts_cd, ', ') FROM svc.wrty_tkt").fetchone()[0]
        size = int(size)
    con.print(t)
    con.print(f"  Category codes: [bold]{codes}[/]   Ticket status codes: [bold]{sts}[/]   Size on disk: [bold]{fmt_mb(size)}[/]")
    con.print("  Nobody outside the data team knows that [bold]TNT[/] means tent or that [bold]O[/] means an open warranty claim.")
    save("tables", dict(db_bytes=size))

def cmd_mapping():
    ttl = open(ONT).read().splitlines(); obda = open(MAP).read()
    pick = [l for l in ttl if re.match(r":(Tent|Product|OpenClaim|WarrantyClaim) ", l)]
    con.print(Panel(Syntax("\n".join(pick), "turtle", theme="monokai", word_wrap=True, background_color="default"), title="Ontology (alderfinch.ttl): the business words", border_style="cyan"))
    blocks = re.findall(r"mappingId\t(tents|claims|open-claims)\ntarget\t\t(.*?)\nsource\t\t(.*?)\n", obda)
    from rich.markup import escape
    txt = "\n".join(f"[bold yellow]mapping[/] {m}\n  [cyan]target[/]  {escape(t)}\n  [green]source[/]  {escape(src)}" for m, t, src in blocks)
    con.print(Panel(txt, title="Mapping (alderfinch.obda): business words -> SQL over live tables", border_style="green"))
    n = len(re.findall(r"^mappingId", obda, re.M))
    con.print(f"  {n} mappings in total. No data is copied: Ontop rewrites each SPARQL query into SQL using these.")

def cmd_ask(name, show_sql=False):
    text = q(name)
    con.print(Panel(Syntax(text.strip(), "sparql", theme="monokai", word_wrap=True, background_color="default"), title=f"SPARQL {name}: {LABEL[name]}", border_style="cyan"))
    (cols, rows), ms = timed(vkg_select, text, n=3)
    show_rows(cols, rows, f"Virtual knowledge graph answer (live PostgreSQL), median {ms:.0f} ms")
    if show_sql:
        sql = vkg_sql(text)
        con.print(Panel(Syntax(sql, "sql", theme="monokai", word_wrap=True, background_color="default"), title="...which Ontop rewrote into this SQL (no triples stored anywhere)", border_style="green"))
    r = load("asks") or {}; r[name] = dict(rows=rows, ms=round(ms, 1)); save("asks", r)

def cmd_etl():
    con.print("[bold yellow]ETL copy:[/] materialize every triple the mapping can produce, then bulk-load a triple store (Oxigraph).")
    shutil.rmtree(COPY_DIR, ignore_errors=True); os.makedirs("export", exist_ok=True); nt = "export/alderfinch.nt"
    t0 = time.time()
    p = subprocess.run([ONTOP, "materialize", "-t", ONT, "-m", MAP, "-p", PROPS, "-f", "ntriples", "-o", nt], capture_output=True, text=True)
    t1 = time.time(); n = re.search(r"NR of TRIPLES: (\d+)", p.stdout + p.stderr)
    con.print(f"  1. ontop materialize -> {nt}: [bold]{int(n.group(1)):,}[/] triples, {fmt_mb(os.path.getsize(nt))}, {t1-t0:.1f} s")
    import pyoxigraph as ox
    st = ox.Store(COPY_DIR); st.bulk_load(path=nt, format=ox.RdfFormat.N_TRIPLES); st.flush(); t2 = time.time()
    con.print(f"  2. bulk load into Oxigraph ./{COPY_DIR}: {len(st):,} triples, {fmt_mb(dir_size(COPY_DIR))} on disk, {t2-t1:.1f} s")
    db = (load("tables") or {}).get("db_bytes")
    con.print(f"  Copy finished at {dt.datetime.now():%H:%M:%S}. Total {t2-t0:.1f} s. From now on the copy ages; the database does not wait for it.")
    if db: con.print(f"  Source tables: {fmt_mb(db)}. Copy: {fmt_mb(os.path.getsize(nt))} file + {fmt_mb(dir_size(COPY_DIR))} store = [bold]{(os.path.getsize(nt)+dir_size(COPY_DIR))/db:.1f}x[/] the source (store alone {dir_size(COPY_DIR)/db:.1f}x).")
    save("etl", dict(triples=int(n.group(1)), nt_bytes=os.path.getsize(nt), store_bytes=dir_size(COPY_DIR), materialize_s=round(t1-t0, 1),
                     load_s=round(t2-t1, 1), total_s=round(t2-t0, 1), at=dt.datetime.now().isoformat(timespec="seconds")))

def cmd_compare():
    st = copy_store(); t = Table(title="Same SPARQL, two engines", box=box.SIMPLE_HEAVY, title_style="bold cyan")
    for c in ("question", "VKG answer", "copy answer", "same?", "VKG ms", "copy ms"): t.add_column(c, justify="left" if c in ("question", "VKG answer", "copy answer") else "right")
    out = {}
    for name in ("q1", "q2", "q3", "q4"):
        (vc, vr), vms = timed(vkg_select, q(name)); (cc, cr), cms = timed(copy_select, st, q(name))
        short = lambda rows: (f"{len(rows)} tents" if name == "q1" else
                              " / ".join(f"{r[0].split()[0]} {r[1]}" if len(r) > 1 else r[0] for r in rows[:2]) + (" ..." if len(rows) > 2 else ""))
        same = sorted(vr) == sorted(cr)
        t.add_row(LABEL[name], short(vr), short(cr), "[green]yes[/]" if same else "[red]NO[/]", f"{vms:.1f}", f"{cms:.1f}")
        out[name] = dict(vkg_ms=round(vms, 1), copy_ms=round(cms, 1), same=same)
    con.print(t)
    con.print("  Medians of 5 runs on this box, warm caches. At this size both are fast; the VKG's speed is your database's speed.")
    save("compare", out)

def cmd_live():
    st = copy_store(); etl = load("etl")
    before_v = vkg_select(q("q2"))[1]; before_c = copy_select(st, q("q2"))[1]
    with psycopg.connect(DSN, autocommit=True) as c:
        now = c.execute("SELECT localtimestamp(0)").fetchone()[0]
        ids = [r[0] for r in c.execute("SELECT t.tkt_id FROM svc.wrty_tkt t JOIN erp.prd_mstr p USING (sku) WHERE p.sup_id='SUP-03' AND t.sts_cd='O' "
                                         "AND t.opn_ts < timestamp '2026-11-06 09:00' ORDER BY t.tkt_id LIMIT 25")]
        c.execute("UPDATE svc.wrty_tkt SET sts_cd='C', cls_ts=%s WHERE tkt_id = ANY(%s)", (now, ids))
        nxt = c.execute("SELECT 'T' || lpad((max(substr(tkt_id,2)::int)+1)::text, 6, '0') FROM svc.wrty_tkt").fetchone()[0]
        c.execute("INSERT INTO svc.wrty_tkt VALUES (%s, 'SO0059990', 'TNT-0302', %s, 'O', 'POLE', NULL)", (nxt, now))
    con.print(f"[bold]Service desk, {now:%H:%M:%S}:[/] closed [bold]{len(ids)}[/] Ridgeway seam claims (repair kits shipped) and opened [bold]{nxt}[/] (tent pole).")
    t0 = time.perf_counter(); after_v = vkg_select(q("q2"))[1]; v24 = vkg_select(q("q5"))[1]; vlag = (time.perf_counter() - t0) * 1000
    after_c = copy_select(st, q("q2"))[1]; c24 = copy_select(st, q("q5"))[1]
    t = Table(title="Who sees the change?", box=box.SIMPLE_HEAVY, title_style="bold cyan")
    for col in ("question", "before", "VKG now (live)", f"copy now (from {etl['at'][11:19]})"): t.add_column(col)
    g = lambda rows: rows[0][1] if rows else "0"
    t.add_row("Ridgeway tent claims open > 14 days", g(before_v), f"[green]{g(after_v)}[/]", f"[red]{g(after_c)}[/]")
    t.add_row("New claims since the snapshot", "0", f"[green]{v24[0][0] if v24 else 0}[/]", f"[red]{c24[0][0] if c24 else 0}[/]")
    con.print(t)
    con.print(f"  VKG: correct on the next query ({vlag:.0f} ms for both). Copy: wrong until the next full ETL run ({etl['total_s']} s of work, usually nightly).")
    save("live", dict(closed=len(ids), new=nxt, before=g(before_v), vkg=g(after_v), copy=g(after_c), vkg_24h=v24[0][0] if v24 else "0",
                      copy_24h=c24[0][0] if c24 else "0", vkg_ms=round(vlag), at=str(now)))

def cmd_schema_change():
    old, new = "sts_cd", "status_cd"
    with psycopg.connect(DSN, autocommit=True) as c: c.execute(f"ALTER TABLE svc.wrty_tkt RENAME COLUMN {old} TO {new}")
    con.print(f"[bold]DBA:[/] ALTER TABLE svc.wrty_tkt RENAME COLUMN {old} TO {new};")
    try: vkg_select(q("q2")); con.print("  VKG still answers (unexpected)")
    except Exception as e:
        m = re.search(r"ERROR: [^\n]*?does not exist", str(e)); con.print(f"  VKG query now fails loudly: [red]{m.group(0) if m else str(e)[:100]}[/]")
    st = copy_store(); cr = copy_select(st, q("q2"))[1]
    con.print(f"  Copy still answers [red]{cr[0][1]}[/] for Ridgeway... silently, from old data. Its next ETL run would fail on the same column.")
    shutil.copy(MAP, f"{RUNS}/alderfinch.obda.bak"); txt = open(MAP).read(); lines = [l for l in txt.splitlines() if old in l]
    t0 = time.time(); open(MAP, "w").write(txt.replace(old, new))
    con.print(f"[bold]Fix:[/] edit the mapping, [bold]{len(lines)} lines[/] in alderfinch.obda ({old} -> {new}). The endpoint (--dev) reloads it.")
    while True:
        try: vr = vkg_select(q("q2"))[1]; break
        except Exception: time.sleep(0.2)
    t_v = time.time() - t0
    con.print(f"  VKG answers again in [green]{t_v:.1f} s[/] after the edit: Ridgeway {vr[0][1]} open claims (live).")
    t1 = time.time()
    p = subprocess.run([ONTOP, "materialize", "-t", ONT, "-m", MAP, "-p", PROPS, "-f", "ntriples", "-o", "export/alderfinch.nt"], capture_output=True, text=True)
    st.clear(); st.bulk_load(path="export/alderfinch.nt", format=__import__("pyoxigraph").RdfFormat.N_TRIPLES); st.flush(); t_c = time.time() - t1
    cr2 = copy_select(st, q("q2"))[1]
    con.print(f"  Copy: same mapping edit, plus a full re-materialize and reload: [yellow]{t_c:.1f} s[/] (Ridgeway {cr2[0][1]}). It scales with data size.")
    save("schema", dict(lines=len(lines), vkg_recover_s=round(t_v, 1), copy_rebuild_s=round(t_c, 1), vkg_after=vr[0][1], copy_after=cr2[0][1]))

def cmd_scorecard():
    tb, e, c, l, s = load("tables"), load("etl"), load("compare"), load("live"), load("schema")
    t = Table(title="ETL copy into a triple store vs virtual knowledge graph (measured on this box)", box=box.SIMPLE_HEAVY, title_style="bold cyan")
    for col in ("", "ETL copy (before)", "Virtual KG (after)"): t.add_column(col)
    kb = sum(os.path.getsize(p) for p in (ONT, MAP))
    t.add_row("Extra storage", f"{fmt_mb(e['nt_bytes']+e['store_bytes'])} ({e['triples']:,} triples)", f"{kb/1000:.1f} KB (ontology + mapping)")
    up = load("up") or {}
    t.add_row("Setup before the first answer", f"{e['total_s']} s copy", f"{up.get('first_answer_s', '?')} s endpoint start")
    t.add_row("After 25 closes + 1 new claim", f"stale: {l['copy']} / {l['copy_24h']} new", f"live: {l['vkg']} / {l['vkg_24h']} new")
    t.add_row("Column renamed", f"silent stale data; {s['copy_rebuild_s']} s rebuild", f"loud error; {s['lines']}-line fix, {s['vkg_recover_s']} s")
    t.add_row("Median query time, q1-q4", " / ".join(f"{c[k]['copy_ms']:.1f}" for k in ("q1", "q2", "q3", "q4")) + " ms",
              " / ".join(f"{c[k]['vkg_ms']:.1f}" for k in ("q1", "q2", "q3", "q4")) + " ms")
    t.add_row("Same answers on fresh data", "yes" if all(c[k]["same"] for k in c) else "no", "yes" if all(c[k]["same"] for k in c) else "no")
    t.add_row("Source of truth", "a second copy", "the operational database")
    con.print(t)
    con.print("  Trade-off: a copy can be faster and works offline. A VKG is always current and costs no second store.")

def cmd_fabric():
    con.print(Panel(
        "[bold]Same ontology, same mapping, different JDBC URL.[/]\n"
        "The tables could live in a Microsoft Fabric Warehouse, or be Lakehouse Delta tables read through its SQL analytics endpoint.\n"
        "Both speak T-SQL over the TDS protocol, so Ontop connects with the SQL Server dialect and the mssql-jdbc driver,\n"
        "signing in with Microsoft Entra ID. Schema names change (dbo instead of crm/erp/svc); the business words do not.\n\n"
        "[dim]fabric.properties.example  (placeholders only, NOT executed in this lesson: no Fabric capacity used)[/]\n"
        + open("vkg/fabric.properties.example").read().strip(), title="Microsoft Fabric tie-in", border_style="cyan"))
    con.print("  Check the generated SQL against the Warehouse T-SQL surface before relying on it in production.")

def cmd_up():
    """Start the Ontop endpoint in dev mode (reloads when the mapping changes) and time it to the first answer."""
    subprocess.run(["pkill", "-f", "ontop.*endpoint"], capture_output=True); time.sleep(1.0)
    port = ENDPOINT.rsplit(":", 1)[1]; t0 = time.time()
    subprocess.Popen([ONTOP, "endpoint", "-t", ONT, "-m", MAP, "-p", PROPS, "--port", port, "--dev"],
                     stdout=open(f"{RUNS}/endpoint.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    while True:
        try: vkg_select(q("q3")); break
        except Exception: time.sleep(0.2)
    s = round(time.time() - t0, 1)
    con.print(f"Ontop endpoint up on port {port} (dev mode, watches the mapping). First SPARQL answer after [bold]{s} s[/]. Nothing was copied.")
    save("up", dict(first_answer_s=s))

def cmd_reset():
    if os.path.exists(f"{RUNS}/alderfinch.obda.bak"): shutil.copy(f"{RUNS}/alderfinch.obda.bak", MAP); os.remove(f"{RUNS}/alderfinch.obda.bak")
    subprocess.run([sys.executable, "db/build_data.py"], check=True); shutil.rmtree(COPY_DIR, ignore_errors=True)
    con.print("reset: data rebuilt, mapping restored, copy removed")

if __name__ == "__main__":
    a = sys.argv[1:] or ["help"]
    if a[0] == "ask": cmd_ask(a[1], "--sql" in a)
    elif a[0] == "schema-change": cmd_schema_change()
    elif a[0] in ("tables", "mapping", "etl", "compare", "live", "scorecard", "fabric", "reset", "up"): globals()["cmd_" + a[0]]()
    else: print(__doc__)
