"""A small, runnable context layer for an AI agent, built over the IoT example.

    python context_layer.py build                       # link the layers into one graph
    python context_layer.py explore site:MTL-01         # walk the linked context of a node
    python context_layer.py ask "QUESTION" --no-context # baseline: an agent with table names only
    python context_layer.py ask "QUESTION"              # grounded: assemble context, apply policies
    python context_layer.py log                         # runtime context, incl. recorded decisions

Layers (all plain files, nothing proprietary):
  data + metadata  data/iot.duckdb (tables, row counts)
  semantics        models/iot.semantic_model.yaml   (Apache Ossie semantic model, folder 04)
  ontology         models/iot.ontology.yaml + iot.mapping.yaml (Apache Ossie ontology, folder 03)
  governance       context/policies.yaml            (our own teaching format)
  runtime          out/runtime_log.jsonl            (events, decisions, actions, outcomes)

TEACHING CODE, NOT A PRODUCT OR STANDARD FEATURE: the graph builder, the context
assembler, the policy checks and the answer composer are written for this lesson.
No LLM is called and no API key is needed. The "understand" step uses a simple fuzzy
matcher as a stand-in for the neural part; the assembled context packet is saved to
out/context_packet.json so you can hand it to any LLM you like.
"""
import difflib, json, os, re, shutil, sys
from datetime import datetime, timedelta
from pathlib import Path

import duckdb, networkx as nx, yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree
from sqlglot import exp, parse_one

from semantic_compiler import Compiler

HERE = Path(__file__).parent
MODELS, CTX, OUT = HERE / "models", HERE / "context", HERE / "out"
DB = HERE / "data" / "iot.duckdb"
LOG = OUT / "runtime_log.jsonl"
con = Console(width=int(os.environ["DEMO_WIDTH"]) if os.environ.get("DEMO_WIDTH") else None, highlight=False)
PAUSE = os.environ.get("DEMO_PAUSE") == "1"
MINT, CYAN, VIOLET, AMBER, ROSE = "#34D399", "#22D3EE", "#A78BFA", "#FBBF24", "#FB7185"
LAYER_COLOR = {"data": CYAN, "semantics": MINT, "ontology": VIOLET, "governance": AMBER, "runtime": ROSE}
AS_OF = datetime(2026, 11, 3, 2, 5)          # "now" for the demo, in UTC (the data ends at 01:59:30)

def load(p): return yaml.safe_load(Path(p).read_text())
def step(n, title):
    if PAUSE and n in (2, 3, 5):              # recording mode: one screen per pause
        input(); con.clear()
    con.print(f"\n[bold {MINT}]{n}[/]  [bold]{title}[/]")
def runtime_rows(): return [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]

# ------------------------------------------------------------------ graph
def build_graph():
    g = nx.MultiDiGraph()
    def node(i, layer, kind, **kw): g.add_node(i, layer=layer, kind=kind, **kw)
    sm, onto, mp = load(MODELS / "iot.semantic_model.yaml"), load(MODELS / "iot.ontology.yaml"), load(MODELS / "iot.mapping.yaml")
    db = duckdb.connect(str(DB), read_only=True)
    # data + metadata: physical tables and the real-world instances in them
    for ds in sm["datasets"]:
        t = ds["source"]; n = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        node(f"table:{t}", "data", "table", rows=n)
    for cid, name in db.execute("SELECT customer_id, customer_name FROM customers").fetchall():
        node(f"customer:{cid}", "data", "instance", label=name)
        g.add_edge(f"customer:{cid}", "concept:Customer", key="instance_of")
    for code, city, cid in db.execute("SELECT site_code, city, customer_id FROM sites").fetchall():
        node(f"site:{code}", "data", "instance", label=city)
        g.add_edge(f"site:{code}", "concept:Site", key="instance_of")
        g.add_edge(f"site:{code}", f"customer:{cid}", key="owned_by")
    for sid, code, bk in db.execute("SELECT device_id, site_code, backup_for FROM devices").fetchall():
        node(f"sensor:{sid}", "data", "instance")
        g.add_edge(f"sensor:{sid}", "concept:Sensor", key="instance_of")
        g.add_edge(f"sensor:{sid}", f"site:{code}", key="installed_at")
        if bk: g.add_edge(f"sensor:{sid}", f"sensor:{bk}", key="backup_for")
    # semantics: datasets, fields, metrics, relationships (Ossie semantic model)
    for ds in sm["datasets"]:
        d = f"dataset:{ds['name']}"
        node(d, "semantics", "dataset", synonyms=(ds.get("ai_context") or {}).get("synonyms", []) if isinstance(ds.get("ai_context"), dict) else [])
        g.add_edge(f"table:{ds['source']}", d, key="source_of")
        for f in ds.get("fields", []):
            fi = f"field:{ds['name']}.{f['name']}"
            node(fi, "semantics", "field", sql=f["expression"]["sql"], synonyms=(f.get("ai_context") or {}).get("synonyms", []))
            g.add_edge(d, fi, key="has_field")
        for m in ds.get("metrics", []):
            mi = f"metric:{ds['name']}.{m['name']}"
            node(mi, "semantics", "metric", sql=m["expression"]["sql"], synonyms=(m.get("ai_context") or {}).get("synonyms", []))
            g.add_edge(d, mi, key="has_metric")
            for c in parse_one(m["expression"]["sql"]).find_all(exp.Column):
                if c.table.lower() != "source": g.add_edge(mi, f"field:{ds['name']}.{c.name}", key="uses")
    for r in sm.get("relationships", []):
        g.add_edge(f"dataset:{r['from']}", f"dataset:{r['to']}", key="joins_to", via=r["from_columns"])
    for m in sm.get("metrics", []):
        mi = f"metric:{m['name']}"
        node(mi, "semantics", "metric", sql=m["expression"]["sql"], synonyms=(m.get("ai_context") or {}).get("synonyms", []))
        for a in parse_one(m["expression"]["sql"]).find_all(exp.Column):     # AGG(ds.metric) vs ds.field
            g.add_edge(mi, f"{'metric' if isinstance(a.parent, exp.Agg) else 'field'}:{a.table}.{a.name}", key="uses")
    # ontology: concepts, relationships, derived rules (Ossie ontology), linked by the mapping
    for c in onto["ontology"]:
        if c["type"] != "EntityType": continue
        ci = f"concept:{c['concept']}"
        node(ci, "ontology", "concept", description=c.get("description", ""), derived_by=c.get("derived_by", []))
        for p in c.get("extends", []): g.add_edge(ci, f"concept:{p}", key="extends")
        for r in c.get("relationships", []):
            tgt = r["roles"][0]["concept"]
            if f"concept:{tgt}" in g or any(x.get("concept") == tgt and x["type"] == "EntityType" for x in onto["ontology"]):
                g.add_edge(ci, f"concept:{tgt}", key=r["name"])
    for cm in mp["concept_mappings"]:
        exprs = re.findall(r"\b(\w+)\.(\w+)\b", json.dumps(cm))
        for ds, fld in exprs:
            if f"field:{ds}.{fld}" in g: g.add_edge(f"concept:{cm['concept']}", f"field:{ds}.{fld}", key="mapped_to")
        if exprs: g.add_edge(f"concept:{cm['concept']}", f"dataset:{exprs[0][0]}", key="mapped_to")
    g.add_edge("concept:AlertReading", "field:readings.is_alert", key="defined_by")
    # governance: policies and what they govern
    for p in load(CTX / "policies.yaml")["policies"]:
        pi = f"policy:{p['id']}"; node(pi, "governance", p["kind"], **{k: v for k, v in p.items() if k not in ("governs", "kind")})
        for t in p["governs"]: g.add_edge(pi, t, key="governs")
    # runtime: events, decisions, actions, outcomes, linked to the things they are about
    for r in runtime_rows():
        ri = f"{r['type']}:{r['id']}"; node(ri, "runtime", r["type"], **{k: v for k, v in r.items() if k not in ("about",)})
        for a in r.get("about", []): g.add_edge(ri, a, key="about")
        if r.get("caused_by"):
            src = next((f"{x['type']}:{x['id']}" for x in runtime_rows() if x["id"] == r["caused_by"]), None)
            if src: g.add_edge(src, ri, key="led_to")
    return g

def short(n): return n.split(":", 1)[1]

def cmd_build():
    OUT.mkdir(exist_ok=True)
    if not LOG.exists() or "--reset" in sys.argv: shutil.copy(CTX / "runtime_seed.jsonl", LOG)
    g = build_graph()
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}", title="Context layer: one linked graph", title_style="bold")
    for c, j in (("Layer", "left"), ("Nodes", "right"), ("Examples", "left")): t.add_column(c, justify=j)
    for layer in LAYER_COLOR:
        ns = [n for n, d in g.nodes(data=True) if d["layer"] == layer]
        t.add_row(f"[{LAYER_COLOR[layer]}]{layer}[/]", str(len(ns)), ", ".join(short(n) for n in ns[:3]) + (" ..." if len(ns) > 3 else ""))
    con.print(t)
    kinds = {}
    for _, _, k in g.edges(keys=True): kinds[k] = kinds.get(k, 0) + 1
    con.print(f"[bold]{g.number_of_nodes()}[/] nodes, [bold]{g.number_of_edges()}[/] edges   " +
              "  ".join(f"[dim]{k}[/] {v}" for k, v in sorted(kinds.items(), key=lambda x: -x[1])[:8]))
    cross = sum(1 for a, b in g.edges() if g.nodes[a]["layer"] != g.nodes[b]["layer"])
    con.print(f"[{MINT}]{cross}[/] edges cross layers: that linking is what makes it a context layer")
    json.dump(nx.node_link_data(g, edges="links"), open(OUT / "context_graph.json", "w"), indent=1, default=str)
    con.print("[dim]saved out/context_graph.json[/]")

def neighborhood(g, start, depth):
    """Breadth-first walk in both directions. A concept is not expanded back into other
    instances, so a site's neighborhood does not pull in every other site."""
    dist, frontier = {start: 0}, [start]
    for d in range(1, depth + 1):
        nxt = []
        for n in frontier:
            for m in set(g.successors(n)) | set(g.predecessors(n)):
                if m in dist or (g.nodes[n]["kind"] == "concept" and g.nodes[m]["layer"] == "data"): continue
                dist[m] = d; nxt.append(m)
        frontier = nxt
    return dist

def cmd_explore(start, depth=4):
    g = build_graph()
    if start not in g: sys.exit(f"unknown node {start}")
    tree = Tree(f"[bold]{start}[/]  [dim]({g.nodes[start]['layer']}, walking {depth} hops)[/]")
    dist = neighborhood(g, start, depth)
    for layer in LAYER_COLOR:
        hits = [n for n in dist if n != start and g.nodes[n]["layer"] == layer]
        if not hits: continue
        br = tree.add(f"[bold {LAYER_COLOR[layer]}]{layer}[/] [dim]{len(hits)}[/]")
        for n in sorted(hits, key=lambda x: (dist[x], x))[:6]:
            d = g.nodes[n]; extra = d.get("text") or d.get("name") or d.get("label") or ""
            br.add(f"{short(n)}  [dim]{extra}[/]")
        if len(hits) > 6: br.add(f"[dim]+{len(hits) - 6} more[/]")
    con.print(tree)

# ------------------------------------------------------------------ ask
def baseline(q):
    con.print(Panel(f"[bold]{q}[/]", title="Agent question (no context)", border_style=ROSE, expand=False))
    con.print("[dim]Scripted baseline: the kind of SQL an agent writes from table names alone.[/]")
    sql = ("SELECT s.site_code, s.site_manager, COUNT(*) AS alerts\nFROM readings r JOIN devices d USING (device_id)\n"
           "JOIN sites s USING (site_code)\nWHERE r.status = 'ALERT'\nGROUP BY ALL ORDER BY alerts DESC LIMIT 1")
    con.print(Syntax(sql, "sql", theme="monokai", background_color="default"))
    code, mgr, n = duckdb.connect(str(DB), read_only=True).execute(sql).fetchone()
    con.print(Panel(f"{code} is the worst site, with {n} alerts. Call {mgr}.", title="Answer without context", border_style=ROSE, expand=False))
    for w in ("Raw count, not a rate: TOR-01 simply has the most sensors",
              "Counts test traffic that the operations team excluded",
              "Exposes a person's name (personal data)", "No evidence and no record of the decision"):
        con.print(f"  [{ROSE}]x[/] {w}")

def understand(g, q):
    """Neural stand-in: fuzzy-match question words to names and ai_context synonyms."""
    words = re.findall(r"[a-z_]+", q.lower()); grams = words + [" ".join(p) for p in zip(words, words[1:])] + [" ".join(p) for p in zip(words, words[1:], words[2:])]
    terms = {}
    for n, d in g.nodes(data=True):
        if d["kind"] not in ("metric", "field", "concept"): continue
        for t in [short(n).split(".")[-1].replace("_", " ")] + list(d.get("synonyms", [])):
            terms.setdefault(t.lower(), n)
    found = {}
    for gram in grams:
        for m in difflib.get_close_matches(gram, terms, n=1, cutoff=0.86):
            found.setdefault(terms[m], (gram, m))
    return found

def assemble(q, role):
    g = build_graph(); rt = runtime_rows()
    con.print(Panel(f"[bold]{q}[/]\n[dim]role: {role}   as of: {AS_OF:%Y-%m-%d %H:%M} UTC[/]", title="Agent question", border_style=MINT, expand=False))
    step(1, "Understand: match words to meaning (fuzzy matcher stands in for the neural step)")
    found = understand(g, q)
    t = Table(box=box.SIMPLE, header_style=f"bold {MINT}")
    for c in ("Words", "Matched", "Node", "Layer"): t.add_column(c)
    for n, (w, m) in found.items(): t.add_row(f'"{w}"', m, short(n), f"[{LAYER_COLOR[g.nodes[n]['layer']]}]{g.nodes[n]['layer']}[/]")
    con.print(t)
    metric = next(n for n in found if n.startswith("metric:"))
    group_ds = "sites"; asked_fields = [n for n in found if n.startswith("field:")]

    step(2, "Retrieve: walk the graph from the matched nodes")
    sem = g.subgraph(n for n in g if g.nodes[n]["layer"] == "semantics")
    keep = set(found)
    for n in found:                           # semantic dependencies: metric -> metrics -> fields
        if n in sem: keep |= nx.descendants(sem, n)
        else: keep |= {m for m in g.successors(n) if g.nodes[m]["layer"] == "semantics"}  # concept -> mapping
    path = nx.shortest_path(sem.to_undirected(as_view=True), "dataset:readings", f"dataset:{group_ds}")
    keep |= set(path) | {"concept:SensorReading", "concept:AlertReading", "field:readings.is_alert"}
    keep |= {p for p in g if g.nodes[p]["layer"] == "governance" and any(v in keep for v in g.successors(p))}
    keep |= {v for p in keep if g.nodes[p]["layer"] == "governance" for v in [g.nodes[p].get("instead")] if v}
    keep |= {r for r in g if g.nodes[r]["layer"] == "runtime" and any(v.startswith("site:") for v in g.successors(r))}
    rank = {"metric": 0, "field": 1, "dataset": 2}
    tree = Tree("[bold]linked context[/]")
    for layer in ("semantics", "ontology", "governance", "runtime"):
        ns = sorted((n for n in keep if g.nodes[n]["layer"] == layer), key=lambda n: (n not in found, rank.get(g.nodes[n]["kind"], 3), n))
        br = tree.add(f"[bold {LAYER_COLOR[layer]}]{layer}[/] [dim]{len(ns)}[/]")
        for n in ns[:5]:
            d = g.nodes[n]
            extra = d.get("sql") or (d.get("derived_by") or [""])[0] or d.get("name") or d.get("text") or ""
            br.add(f"{short(n)}  [dim]{str(extra)[:100]}[/]")
        if len(ns) > 5: br.add(f"[dim]+{len(ns) - 5} more[/]")
    con.print(tree)
    con.print(f"[dim]join path from relationships:[/] {' -> '.join(short(p) for p in path)}")

    step(3, "Apply policies (symbolic rules, checked in code)")
    checks, blocked, where, evidence = [], [], [], []
    db = duckdb.connect(str(DB), read_only=True)
    for p in (g.nodes[n] | {"_id": n} for n in sorted(keep) if g.nodes[n]["layer"] == "governance"):
        pid = short(p["_id"])
        if p["kind"] == "access":
            hit = [f for f in asked_fields if f in g.successors(p["_id"])]
            if hit and role in p["deny_roles"]:
                blocked += hit; checks.append((pid, "BLOCK", f"{short(hit[0])} denied for {role}; use {short(p['instead'])}"))
                asked_fields = [f for f in asked_fields if f not in hit] + [p["instead"]]
            else: checks.append((pid, "PASS", "no personal data requested"))
        elif p["kind"] == "certification":
            ok = metric in g.successors(p["_id"])
            checks.append((pid, "PASS" if ok else "BLOCK", f"{short(metric)} is {'certified' if ok else 'not certified'}"))
        elif p["kind"] == "freshness":
            last = db.execute("SELECT MAX(ts) FROM readings").fetchone()[0]
            lag = (AS_OF - last).total_seconds() / 60
            checks.append((pid, "PASS" if lag <= p["max_lag_minutes"] else "BLOCK", f"newest reading {lag:.1f} min old (max {p['max_lag_minutes']})"))
    for r in rt:
        if r.get("exclude"):
            x = r["exclude"]
            where.append(f"NOT (sites.site_code = '{x['site']}' AND readings.reading_ts >= TIMESTAMP '{x['from']}' AND readings.reading_ts < TIMESTAMP '{x['to']}')")
            checks.append((r["id"], "APPLY", f"exclude {x['site']} {x['from'][5:16]} to {x['to'][5:16]} (test traffic)"))
    t = Table(box=box.SIMPLE, header_style=f"bold {AMBER}")
    for c in ("Rule", "Result", "Why"): t.add_column(c)
    for pid, res, why in checks:
        col = {"PASS": MINT, "BLOCK": ROSE, "APPLY": AMBER}[res]; t.add_row(pid, f"[bold {col}]{res}[/]", why)
    con.print(t)

    step(4, "Compute the governed metric on DuckDB (teaching compiler from folder 04)")
    comp = Compiler(load(MODELS / "iot.semantic_model.yaml"))
    sql = comp.compile([short(metric), "readings.alert_count", "readings.reading_count"], ["sites.site_code"], " AND ".join(where) or None)
    con.print(Syntax(sql, "sql", theme="monokai", background_color="default", word_wrap=True))
    rows = sorted(db.execute(sql).fetchall(), key=lambda r: -r[1])
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}")
    for c, j in (("site", "left"), ("alert_rate_pct", "right"), ("alerts", "right"), ("readings", "right")): t.add_column(c, justify=j)
    for i, r in enumerate(rows): t.add_row(*(f"[bold {MINT}]{v}[/]" if i == 0 else str(v) for v in (r[0], f"{r[1]:.2f}", r[2], r[3])))
    con.print(t)

    step(5, "Answer, grounded in the assembled context")
    top = rows[0][0]
    info = db.execute("SELECT s.city, c.customer_name, s.on_call_channel FROM sites s JOIN customers c USING (customer_id) WHERE site_code = ?", [top]).fetchone()
    recent = [r for r in rt if f"site:{top}" in r.get("about", []) and r["type"] != "answer"]
    since = None
    if recent:
        last_out = max((r for r in recent if r["type"] == "outcome"), key=lambda r: r["at"], default=None)
        if last_out:
            ts = last_out["at"].replace("T", " ").rstrip("Z")
            since = db.execute("""SELECT COUNT(*) FILTER (WHERE r.status = 'ALERT') FROM readings r JOIN devices d USING (device_id)
                                  WHERE d.site_code = ? AND r.ts > CAST(? AS TIMESTAMP)""", [top, ts]).fetchone()[0]
    tor = next(r for r in rows if r[0] == "TOR-01")
    ans = (f"{top} ({info[0]}, {info[1]}) has the worst certified alert rate: {rows[0][1]:.2f}%.\n"
           f"TOR-01 is {tor[1]:.2f}% once its HVAC test window is excluded (DEC-102).\n")
    if since is not None:
        ans += f"Recent context: {last_out['text'].lower()} ({last_out['id']}); {since} alert{'' if since == 1 else 's'} at {top} since then.\n"
    ans += f"Escalate via {info[2]}. The site manager's name is withheld (POL-PII-01)."
    con.print(Panel(ans, title="Answer with context", border_style=MINT, expand=False))
    evidence = [short(metric), "DEC-102"] + ([last_out["id"]] if since is not None else []) + [c[0] for c in checks if c[0].startswith("POL")]
    con.print(f"[dim]evidence:[/] {', '.join(evidence)}")
    packet = dict(question=q, role=role, as_of=AS_OF.isoformat(), matched={short(k): v[1] for k, v in found.items()},
                  context=sorted(short(n) for n in keep), policy_checks=checks, sql=sql, result=rows, answer=ans, blocked=[short(b) for b in blocked])
    json.dump(packet, open(OUT / "context_packet.json", "w"), indent=1, default=str)

    step(6, "Remember: write the decision back as runtime context")
    n = sum(1 for r in rt if r["id"].startswith("ANS-")) + 106
    rec = dict(id=f"ANS-{n}", type="answer", at=(AS_OF + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:00Z"), about=[f"site:{top}"],
               text=f"Agent ranked {top} worst by {short(metric)} ({rows[0][1]:.2f}%); blocked {', '.join(short(b) for b in blocked) or 'nothing'}",
               evidence=evidence)
    with open(LOG, "a") as f: f.write(json.dumps(rec) + "\n")
    con.print(Panel("\n".join(f"[{ROSE}]{k}[/]: {', '.join(v) if isinstance(v, list) else v}" for k, v in rec.items()),
                    title="New runtime context", border_style=ROSE, expand=False))
    con.print(f"[dim]appended to out/runtime_log.jsonl; packet saved to out/context_packet.json[/]")

def cmd_log(k=4):
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {ROSE}", title="Runtime context (newest last)", title_style="bold")
    for c in ("id", "type", "at (UTC)", "about", "text"): t.add_column(c)
    for r in runtime_rows()[-k:]:
        t.add_row(r["id"], r["type"], r["at"][5:16].replace("T", " "), ", ".join(r.get("about", [])), r["text"])
    con.print(t)

if __name__ == "__main__":
    a = sys.argv[1:] or ["build"]
    if not LOG.exists() and a[0] != "build": OUT.mkdir(exist_ok=True); shutil.copy(CTX / "runtime_seed.jsonl", LOG)
    if a[0] == "build": cmd_build()
    elif a[0] == "explore": cmd_explore(a[1])
    elif a[0] == "ask":
        role = a[a.index("--role") + 1] if "--role" in a else "ops_agent"
        baseline(a[1]) if "--no-context" in a else assemble(a[1], role)
    elif a[0] == "log": cmd_log(int(a[1]) if len(a) > 1 else 4)
    else: print(__doc__)
