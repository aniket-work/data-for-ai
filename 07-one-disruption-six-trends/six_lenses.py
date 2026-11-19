"""One flight disruption, six data and AI lenses. The same fictional scenario (Larkspur Air cancels F-210
at NOR-1 in freezing rain) handled six ways, then compared in one scorecard.
Everything here is OUR OWN TEACHING CODE (Python, PyYAML, networkx, rich), not a product feature.
No LLM is called and no API key is needed: mock_llm() is a clearly labelled template that stands in for one.

  python six_lenses.py stream       # 1 agentic data streaming: react to events in real time
  python six_lenses.py quality      # 2 agentic data management: detect, fix or quarantine bad records
  python six_lenses.py residency    # 3 sovereign AI: residency-tagged data map, block cross-region use
  python six_lenses.py decide [--explain P-007]   # 4 decision governance: modeled decision + audit log
  python six_lenses.py govern       # 5 AI governance platform: policy-as-code on agent actions
  python six_lenses.py graphrag     # 6 GraphRAG vs plain keyword RAG
  python six_lenses.py ask [1-6]    # the same six questions to every lens
  python six_lenses.py scorecard
"""
import csv, json, os, re, sys, time, textwrap, pathlib, datetime as dt
import yaml, networkx as nx
from rich.console import Console
from rich.table import Table
from rich import box

HERE = pathlib.Path(__file__).parent; DATA = HERE / "data"; OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
con = Console(width=int(os.environ.get("DEMO_WIDTH", 120)), highlight=False)
COL = {"stream": "bright_blue", "quality": "yellow", "residency": "cyan", "decide": "magenta", "govern": "green", "graphrag": "bright_red"}
def rows(n): return list(csv.DictReader(open(DATA / n)))
def ts(s): return dt.datetime.fromisoformat(s)
def title(t, c): con.print(f"\n[bold {c}]▌ {t}[/]")
def wrap(label, text, pad=12): con.print(label + textwrap.fill(text, width=con.width - 4, initial_indent="#" * pad, subsequent_indent="    ")[pad:].replace("[", "\\["))

def mock_llm(template, **facts):
    """Stand-in for a language model: fills a fixed template with the facts it is given. No model is called."""
    return template.format(**facts)

# ------------------------------------------------------------------ lens 1: agentic data streaming
def process_stream(live=False):
    state = {"delays": [], "alerts": [], "trigger": None, "proc_ms": []}
    for line in open(DATA / "events.jsonl"):
        e = json.loads(line); t0 = time.perf_counter(); note = ""
        if e["type"] == "delay" and e.get("minutes", 0) > 0:
            state["delays"] = [d for d in state["delays"] if (ts(e["ts"]) - d).total_seconds() <= 1800] + [ts(e["ts"])]
            if len(state["delays"]) >= 3 and "risk" not in state["alerts"]:
                state["alerts"].append("risk"); note = "[yellow]3 delays in 30 min → disruption risk alert[/]"
        if e["type"] == "cancellation":
            state["trigger"] = e; t1 = time.perf_counter(); _, dec = decide()
            state["react_ms"] = (time.perf_counter() - t1) * 1000; state["n_decisions"] = len(dec)
            note = f"[bold red]CANCELLED {e['flight']} → agent: {len(dec)} rebookings in {state['react_ms']:.0f} ms[/]"
        if e["type"] == "seat_release" and state["trigger"]: note = f"[green]{e['seats_free']} seats on {e['flight']} → passed to the agent[/]"
        if e["type"] == "crew_duty_update": note = f"[green]duty of {e['crew']} → {e['duty_hours_logged']} h, graph updated[/]"
        ms = (time.perf_counter() - t0) * 1000; state["proc_ms"].append(ms)
        if live:
            detail = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("event_id", "ts", "type"))
            con.print(f"  {e['ts'][11:]}  [bold]{e['type']:<17}[/] {(detail if len(detail) <= 56 else detail[:55] + "…"):<56} {note}")
            time.sleep(0.35 if e["type"] != "cancellation" else 0.9)
    return state

def cmd_stream():
    title("Lens 1 · Agentic data streaming: events in, actions out, in real time", COL["stream"])
    con.print("  [dim]replaying the morning's operations events (event times are simulated; processing time is measured)[/]")
    st = process_stream(live=True); trig = st["trigger"]
    batch = ts(trig["ts"]).replace(hour=2, minute=0) + dt.timedelta(days=1)
    gap = batch - ts(trig["ts"])
    con.print(f"  [bold]streaming:[/] {len(st['proc_ms'])} events, cancellation at {trig['ts'][11:]} → {st['n_decisions']} rebooking decisions ready {st['react_ms']:.0f} ms later (measured)")
    con.print(f"  [bold]nightly batch:[/] the same event would be seen at {batch:%Y-%m-%d %H:%M}, {gap.seconds // 3600} h {gap.seconds % 3600 // 60} min later")

# ------------------------------------------------------------------ lens 2: agentic data management
def quality_agent():
    pax = {p["passenger_id"]: p for p in rows("passengers.csv")}
    flights = {f["flight_id"]: f for f in rows("flights.csv")}
    airports = {a["airport_id"] for a in rows("airports.csv")}
    raw = rows("bookings.csv"); findings = []; seen = set(); clean = []; quarantine = []
    for i, b in enumerate(raw, 2):
        key = tuple(b.values())
        if key in seen: findings.append(("duplicate_row", b["passenger_id"], i, "auto-fix: drop exact duplicate")); continue
        seen.add(key)
        if b["origin"] not in airports and b["origin"].upper() in airports:
            findings.append(("airport_code_case", b["passenger_id"], i, f"auto-fix: {b['origin']} → {b['origin'].upper()}")); b["origin"] = b["origin"].upper()
        if float(b["fare_cad"]) < 0:
            findings.append(("negative_fare", b["passenger_id"], i, "quarantine: needs a human")); quarantine.append(b); continue
        if not b["contact_on_file"]:
            findings.append(("missing_contact", b["passenger_id"], i, "recommend: notify at the airport desk"))
        clean.append(b)
    # pattern across rows: one passenger on two flights that overlap in time
    by_pax = {}
    for b in clean: by_pax.setdefault(b["passenger_id"], []).append(b)
    for pid, bs in by_pax.items():
        if len(bs) > 1:
            fs = sorted((ts(flights[b["flight_id"]]["departs"]), ts(flights[b["flight_id"]]["arrives"]), b) for b in bs)
            if fs[1][0] < fs[0][1]:
                findings.append(("overlapping_flights", pid, 0, "quarantine: needs a human"))
                for _, _, b in fs: clean.remove(b); quarantine.append(b)
    q_pax = sorted({b["passenger_id"] for b in quarantine})
    report = dict(rows_in=len(raw), rows_clean=len(clean), quarantined=len(quarantine), quarantined_passengers=q_pax,
                  auto_fixed=sum(f[3].startswith("auto-fix") for f in findings), findings=findings,
                  score_before=round(100 * (len(raw) - len(findings)) / len(raw), 1), score_after=round(100 * (len(clean) - sum(f[0] == "missing_contact" for f in findings)) / len(clean), 1))
    json.dump(report, open(OUT / "dq_report.json", "w"), indent=1, default=list)
    return clean, report

def cmd_quality():
    title("Lens 2 · Agentic data management: detect → recommend → act → monitor", COL["quality"])
    clean, r = quality_agent()
    t = Table(box=box.SIMPLE_HEAD, header_style="bold yellow", pad_edge=False)
    for c in ["Pattern found", "Passenger", "Row", "What the agent did"]: t.add_column(c)
    for k, pid, row, act in r["findings"]:
        c = "green" if act.startswith("auto") else ("red" if act.startswith("quar") else "yellow")
        t.add_row(k, pid, str(row) if row else "-", f"[{c}]{act}[/]")
    con.print(t)
    con.print(f"  rows {r['rows_in']} → {r['rows_clean']} clean, {r['quarantined']} rows quarantined for {len(r['quarantined_passengers'])} passengers ({', '.join(r['quarantined_passengers'])}), {r['auto_fixed']} auto-fixed")
    con.print(f"  [bold]monitor:[/] quality score {r['score_before']}% → {r['score_after']}%   [dim]rule: auto-fix only safe, reversible changes; quarantine the rest for a human[/]")

# ------------------------------------------------------------------ lens 3: sovereign AI and data residency
def residency_check(dataset, records, endpoint, cfg, aggregate=False):
    ds = cfg["datasets"][dataset]; where = cfg["endpoints"][endpoint]["runs_in"]
    if not ds["personal_data"] or aggregate: return True, "RES-02"
    homes = {r[ds["tag_field"]] for r in records} if ds["residency"] == "per_record" else {ds["residency"]}
    return homes == {where}, "RES-01"

def route_messages(pax_ids):
    cfg = yaml.safe_load(open(HERE / "config" / "residency.yaml")); pax = {p["passenger_id"]: p for p in rows("passengers.csv")}
    log = []
    for pid in pax_ids:
        p = pax[pid]; ep = "assist-north" if p["home_jurisdiction"] == "Norland" else "assist-south"
        ok, rule = residency_check("passengers", [p], ep, cfg); log.append(dict(passenger=pid, endpoint=ep, allowed=ok, rule=rule))
    json.dump(log, open(OUT / "routing_log.json", "w"), indent=1)
    return cfg, pax, log

def cmd_residency():
    title("Lens 3 · Sovereign AI and data residency: where may this data go?", COL["residency"])
    clean, _ = quality_agent(); ids = sorted({b["passenger_id"] for b in clean})
    cfg, pax, log = route_messages(ids)
    t = Table(box=box.SIMPLE_HEAD, header_style="bold cyan", pad_edge=False)
    for c in ["Dataset", "Personal data", "Residency tag"]: t.add_column(c)
    for k, v in cfg["datasets"].items(): t.add_row(k, "yes" if v["personal_data"] else "no", v["residency"] if v["residency"] != "per_record" else f"per record ({v['tag_field']})")
    e = Table(box=box.SIMPLE_HEAD, header_style="bold cyan", pad_edge=False)
    e.add_column("AI endpoint"); e.add_column("Runs in")
    for k, v in cfg["endpoints"].items(): e.add_row(k, v["runs_in"])
    g = Table.grid(padding=(0, 6)); g.add_row(t, e); con.print(g)
    recs = [pax[i] for i in ids]
    tries = [("all passenger records → assist-global", "passengers", recs, "assist-global", False),
             ("Norland passengers → assist-north", "passengers", [r for r in recs if r["home_jurisdiction"] == "Norland"], "assist-north", False),
             ("Solmara passengers → assist-north", "passengers", [r for r in recs if r["home_jurisdiction"] == "Solmara"], "assist-north", False),
             ("rebooking counts, no IDs → assist-global", "passengers", recs, "assist-global", True),
             ("flight schedule → assist-global", "flights", rows("flights.csv"), "assist-global", False)]
    for label, ds, rr, ep, agg in tries:
        ok, rule = residency_check(ds, rr, ep, cfg, agg)
        con.print(f"  {'[bold green]ALLOW[/]' if ok else '[bold red]BLOCK[/]'}  {label:<44} [dim]{rule}: {next(x['text'] for x in cfg['rules'] if x['id'] == rule)}[/]")
    n = sum(1 for l in log if l["endpoint"] == "assist-north"); s = len(log) - n
    con.print(f"  [bold]routing:[/] {n} Norland passengers → assist-north, {s} Solmara passengers → assist-south, 0 blocked, 0 sent offshore")

# ------------------------------------------------------------------ lens 4: decision governance
def decide():
    table = yaml.safe_load(open(HERE / "decisions" / "rebooking.dmn.yaml"))
    clean, _ = quality_agent(); pax = {p["passenger_id"]: p for p in rows("passengers.csv")}
    fl = {f["flight_id"]: f for f in rows("flights.csv")}; mct = 60
    ids = sorted({b["passenger_id"] for b in clean if b["flight_id"] == "F-210"})
    out = []
    for pid in ids:
        p = pax[pid]; onw = p["onward_flight"]
        ok = bool(onw) and (ts(fl[onw]["departs"]) - ts(fl["F-214"]["arrives"])).total_seconds() / 60 >= mct
        inp = dict(needs_assistance=p["needs_assistance"], connection_ok_on_f214=ok, has_connection=bool(onw), tier=p["tier"])
        rule = next(r for r in table["rules"] if all(inp[k] == v for k, v in r["when"].items()))
        out.append(dict(passenger=pid, inputs=inp, rule=rule["id"], why=rule["why"], **rule["then"]))
    cap = table["capacity"]["F-214"]; seats = int(fl["F-214"]["seats_free"])
    for d in sorted([d for d in out if d["option"] == "F-214"], key=lambda d: (d["priority"], d["passenger"])):
        if seats > 0: seats -= 1
        else: d.update(option=cap["overflow_to"], rule=cap["overflow_rule"], why=cap["overflow_why"], voucher_cad=cap["overflow_voucher_cad"])
    with open(OUT / "audit_log.jsonl", "w") as f:
        for d in out:
            f.write(json.dumps(dict(decision=table["decision"], version=table["version"], hit_policy=table["hit_policy"], decided_at="2026-11-12T06:40:02", **d)) + "\n")
    return table, out

def cmd_decide(explain=None):
    title("Lens 4 · Decision governance: a modeled, explainable, audited decision", COL["decide"])
    table, out = decide()
    if not explain:
        t = Table(box=box.SIMPLE_HEAD, header_style="bold magenta", pad_edge=False)
        for c in ["Rule", "When", "Then", "Passengers"]: t.add_column(c)
        cnt = {}
        for d in out: cnt[d["rule"]] = cnt.get(d["rule"], 0) + 1
        for r in table["rules"] + [dict(id="CAP", when={"F-214 full": True}, then={"option": "F-218", "voucher_cad": 205})]:
            w = ", ".join(f"{k}={v}" for k, v in r["when"].items()) or "otherwise"
            t.add_row(r["id"], w, f"{r['then']['option']}, voucher {r['then']['voucher_cad']}", str(cnt.get(r["id"], 0)))
        con.print(t)
        con.print(f"  {len(out)} decisions (2 quarantined passengers held back), hit policy FIRST, table version {table['version']} → out/audit_log.jsonl")
    pid = explain or "P-007"; d = next(x for x in out if x["passenger"] == pid)
    con.print(f"  [bold]explain {pid}:[/] inputs {d['inputs']}")
    con.print(f"    → rule [magenta]{d['rule']}[/]: {d['option']}, voucher {d['voucher_cad']} CAD. {d['why']}")
    rec = next(json.loads(l) for l in open(OUT / "audit_log.jsonl") if json.loads(l)["passenger"] == pid)
    con.print(f"  [dim]audit record: {json.dumps({k: rec[k] for k in ('version', 'passenger', 'rule', 'option', 'voucher_cad', 'decided_at')})}[/]")

# ------------------------------------------------------------------ lens 5: AI governance platform
def govern():
    pol = yaml.safe_load(open(HERE / "governance" / "policies.yaml")); table, out = decide()
    _, _, log = route_messages([d["passenger"] for d in out])
    actions = [dict(model="rebook-assistant", action="rebook", passenger=d["passenger"], flight=d["option"]) for d in out]
    actions += [dict(model="rebook-assistant", action="issue_voucher", passenger=d["passenger"], amount_cad=d["voucher_cad"]) for d in out]
    actions.append(dict(model="rebook-assistant", action="cancel_ticket", passenger="P-031", reason="agent proposal: overlapping booking"))
    audited = {json.loads(l)["passenger"] for l in open(OUT / "audit_log.jsonl")}
    res = []
    for a in actions:
        verdict, why = "allow", []
        for p in pol["policies"]:
            if p["check"] == "model_registered" and not pol["models"].get(a["model"], {}).get("registered"): verdict, why = "deny", why + [p["id"]]
            if p["check"] == "voucher_limit" and a["action"] == "issue_voucher" and a["amount_cad"] > p["limit_cad"] and verdict == "allow": verdict, why = "needs approval", why + [p["id"]]
            if p["check"] == "denied_action" and a["action"] == p["action"]: verdict, why = "deny", why + [p["id"]]
        res.append((a, verdict, why))
    checks = {"GOV-04": (len(audited & {d["passenger"] for d in out}), len(out)), "GOV-05": (sum(l["allowed"] for l in log), len(log))}
    json.dump(dict(results=[dict(action=a, verdict=v, policies=w) for a, v, w in res], checks=checks), open(OUT / "governance_report.json", "w"), indent=1)
    return pol, res, checks

def cmd_govern():
    title("Lens 5 · AI governance platform: central policies, checked as code before actions run", COL["govern"])
    pol, res, checks = govern()
    for p in pol["policies"]: con.print(f"  [green]{p['id']}[/] {p['name']}")
    m = pol["models"]["rebook-assistant"]
    con.print(f"  model registry: rebook-assistant, owner {m['owner']}, risk tier {m['risk_tier']} → [bold green]registered[/] (GOV-01)")
    n = lambda v: sum(1 for _, vv, _ in res if vv == v)
    con.print(f"  {len(res)} planned agent actions → [bold green]{n('allow')} allow[/], [bold yellow]{n('needs approval')} needs approval[/], [bold red]{n('deny')} deny[/]")
    for a, v, w in res:
        if v != "allow":
            c = "yellow" if v == "needs approval" else "red"
            det = f"{a['amount_cad']} CAD voucher for {a['passenger']}" if a["action"] == "issue_voucher" else f"{a['action']} {a['passenger']} ({a.get('reason', '')})"
            con.print(f"    [bold {c}]{v.upper():<15}[/] {det}  [dim]{', '.join(w)}[/]")
    for k, (a, b) in checks.items(): con.print(f"  [bold green]✔[/] {k}: {a}/{b} " + ("decisions have an audit record" if k == "GOV-04" else "model calls passed the residency check"))

# ------------------------------------------------------------------ lens 6: GraphRAG vs plain keyword RAG
QUESTION = "Which disrupted passengers can still make their onward connection on F-214, and which crew can legally fly F-214?"
STOP = set("which can still make their on and the a of to is fly f any who".split())
def notes(): return {p.stem: p.read_text() for p in sorted((HERE / "knowledge" / "ops_notes").glob("*.md"))}
def words(s): return [w for w in re.findall(r"[a-z0-9-]+", s.lower()) if w not in STOP]

def keyword_rag(k=3):
    q = set(words(QUESTION)); docs = notes()
    scored = sorted(((len(q & set(words(t))), n) for n, t in docs.items()), reverse=True)[:k]
    ctx = [docs[n].split("\n", 1)[1].strip().split(". ")[0].rstrip(".") + "." for _, n in scored]
    return scored, mock_llm("Based on the documents: {ctx}", ctx=" ".join(ctx))

def build_graph():
    G = nx.MultiDiGraph()
    for a in rows("airports.csv"): G.add_node(a["airport_id"], kind="Airport", jurisdiction=a["jurisdiction"])
    for f in rows("flights.csv"):
        G.add_node(f["flight_id"], kind="Flight", departs=f["departs"], arrives=f["arrives"])
        G.add_edge(f["flight_id"], f["origin"], rel="FROM"); G.add_edge(f["flight_id"], f["destination"], rel="TO")
        G.add_edge(f["flight_id"], f["crew_id"], rel="OPERATED_BY")
    for c in rows("crews.csv"):
        G.add_node(c["crew_id"], kind="Crew", duty=float(c["duty_hours_logged"]), status=c["status"]); G.add_edge(c["crew_id"], c["base"], rel="BASED_AT")
    for p in rows("passengers.csv"):
        G.add_node(p["passenger_id"], kind="Passenger"); G.add_edge(p["passenger_id"], "F-210", rel="BOOKED_ON")
        if p["onward_flight"]: G.add_edge(p["passenger_id"], p["onward_flight"], rel="CONNECTS_TO")
    facts = {}
    for n, t in notes().items():                       # simple regex extraction stands in for LLM entity extraction
        G.add_node(n, kind="Note")
        for ent in set(re.findall(r"\b(?:[FC]-\d+|NOR-\d|SOL-\d)\b", t)): G.add_edge(n, ent, rel="MENTIONS")
        for key, rx, cast in [("duty_limit", r"not exceed (\d+) duty hours", float), ("briefing", r"plus (\d+) hour of briefing", float),
                              ("mct", r"minimum connection time at SOL-1.* (\d+) minutes", int), ("block", r"block time of F-214 is ([\d.]+) hours", float)]:
            if m := re.search(rx, t): facts[key] = cast(m.group(1)); facts.setdefault("_src", set()).add(n)
    return G, facts

def graph_rag():
    G, f = build_graph(); arr = ts(G.nodes["F-214"]["arrives"]); path = []
    makes, misses = [], []
    for p, _, d in G.in_edges("F-210", data=True):
        if d["rel"] != "BOOKED_ON": continue
        for _, onw, d2 in G.out_edges(p, data=True):
            if d2["rel"] == "CONNECTS_TO":
                gap = (ts(G.nodes[onw]["departs"]) - arr).total_seconds() / 60
                (makes if gap >= f["mct"] else misses).append((p, onw, int(gap)))
    crew = next(v for _, v, d in G.out_edges("F-214", data=True) if d["rel"] == "OPERATED_BY")
    need = f["block"] + f["briefing"]; legal = lambda c: G.nodes[c]["duty"] + need <= f["duty_limit"]
    swap = None
    if not legal(crew):
        swap = next(c for c, _, d in G.in_edges("NOR-1", data=True) if d["rel"] == "BASED_AT" and G.nodes[c]["status"] == "reserve" and legal(c))
    used = ["F-214", crew, swap] + sorted({o for _, o, _ in makes + misses})
    evidence = sorted({n for e in used for n in G.predecessors(e) if G.nodes[n]["kind"] == "Note"} | f["_src"])
    ans = mock_llm("{n_make} passengers make their onward connection on F-214: {make}. {n_miss} miss it: {miss}. "
                   "Crew {crew} cannot legally fly F-214 ({d1:g} + {need:g} = {t1:g} h, over the {lim:g} h limit); reserve crew {swap} can ({d2:g} + {need:g} = {t2:g} h).",
                   n_make=len(makes), make=", ".join(f"{p} ({o})" for p, o, _ in sorted(makes)), n_miss=len(misses),
                   miss=", ".join(f"{p} ({o})" for p, o, _ in sorted(misses)), crew=crew, d1=G.nodes[crew]["duty"], need=need,
                   t1=G.nodes[crew]["duty"] + need, lim=f["duty_limit"], swap=swap, d2=G.nodes[swap]["duty"], t2=G.nodes[swap]["duty"] + need)
    return G, f, makes, misses, crew, swap, evidence, ans

def cmd_graphrag():
    title("Lens 6 · GraphRAG vs plain keyword RAG: the same question", COL["graphrag"])
    con.print(f"  [bold]Q:[/] {QUESTION}")
    scored, ans = keyword_rag()
    con.print(f"\n  [bold]Plain keyword RAG[/] retrieves top 3 notes by word overlap: " + ", ".join(f"{n} ({s})" for s, n in scored))
    wrap("  [dim]mock LLM:[/] ", ans)
    con.print("  [bold red]✘[/] names crew C-7 (not legal today) and lists no passengers: the facts sit in different notes and tables")
    G, f, makes, misses, crew, swap, ev, ans2 = graph_rag()
    con.print(f"\n  [bold]GraphRAG[/] graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges (tables + 8 notes linked by the entities they mention)")
    con.print(f"  path: F-210 ← BOOKED_ON ← passenger → CONNECTS_TO → onward flight; F-214 → OPERATED_BY → {crew}; reserve crews → BASED_AT → NOR-1")
    con.print(f"  facts from notes: duty limit {f['duty_limit']:g} h, briefing {f['briefing']:g} h, block {f['block']:g} h, minimum connection {f['mct']} min")
    con.print(f"  evidence notes: {', '.join(ev)}")
    wrap("  [dim]mock LLM:[/] ", ans2)
    con.print("  [bold green]✔[/] connected answer, with the path and the notes it used as evidence")

# ------------------------------------------------------------------ the same questions to every lens
LENSES = ["Data residency", "Decision governance", "AI governance", "Data streaming", "Data quality agent", "GraphRAG", "Plain keyword RAG"]
QUESTIONS = {1: "May passenger data go to the offshore model?", 2: "Why is P-007 on tomorrow's flight?",
             3: "May the agent issue a 450 CAD voucher alone?", 4: "How fast did we react to the cancellation?",
             5: "Which records were unsafe to act on?", 6: "Who still connects, and which crew is legal for F-214?"}
Y, P_, N = "[bold green]✔[/]", "[bold yellow]~[/]", "[bold red]✘[/]"

def answers():
    st = process_stream(); clean, dq = quality_agent(); table, out = decide(); pol, res, checks = govern()
    _, _, makes, misses, crew, swap, _, _ = graph_rag(); d7 = next(d for d in out if d["passenger"] == "P-007")
    v450 = next(v for a, v, _ in res if a.get("amount_cad") == 450)
    A = {1: ("Data residency", "BLOCK: personal data stays in Norland or Solmara (RES-01)"),
         2: ("Decision governance", f"rule {d7['rule']}: {d7['why']}"),
         3: ("AI governance", f"{v450}: GOV-02, above the 300 CAD limit"),
         4: ("Data streaming", f"{st['n_decisions']} rebookings {st['react_ms']:.0f} ms after the event, not at the 02:00 batch"),
         5: ("Data quality agent", f"{len(dq['quarantined_passengers'])} passengers quarantined ({', '.join(dq['quarantined_passengers'])}), 2 rows auto-fixed"),
         6: ("GraphRAG", f"{len(makes)} connect ({', '.join(p for p, _, _ in sorted(makes))}); swap {crew} → {swap}")}
    M = {"Data residency":      [Y, N, N, N, N, N], "Decision governance": [N, Y, P_, N, N, N], "AI governance": [P_, P_, Y, N, N, N],
         "Data streaming":      [N, N, N, Y, N, N], "Data quality agent":  [N, N, N, N, Y, N], "GraphRAG":      [N, P_, N, N, N, Y],
         "Plain keyword RAG":   [N, N, N, N, N, N]}
    return A, M

def cmd_ask(nums):
    A, M = answers()
    t = Table(box=box.SIMPLE_HEAD, header_style="bold yellow", pad_edge=False)
    for c in ["#", "Question", "Answered by", "Answer"]: t.add_column(c)
    for q in nums: t.add_row(f"Q{q}", QUESTIONS[q], f"[bold]{A[q][0]}[/]", A[q][1])
    title("The same questions, one scenario", "yellow"); con.print(t)

def cmd_scorecard():
    A, M = answers()
    adds = {"Data residency": "where data and models may run", "Decision governance": "why each decision was made",
            "AI governance": "what agents are allowed to do", "Data streaming": "react in milliseconds, not overnight",
            "Data quality agent": "trustworthy records to act on", "GraphRAG": "connected answers with evidence",
            "Plain keyword RAG": "(baseline) similar text, not connected facts"}
    title("Scorecard · one disruption, six lenses (+ a plain RAG baseline)", "yellow")
    t = Table(box=box.ROUNDED, header_style="bold yellow", border_style="grey50")
    t.add_column("Lens"); [t.add_column(f"Q{q}", justify="center") for q in QUESTIONS]; t.add_column("Adds")
    for l in LENSES: t.add_row(f"[bold]{l}[/]", *M[l], adds[l])
    con.print(t)
    for q, s in QUESTIONS.items(): con.print(f"  [dim]Q{q}[/] {s}")
    con.print("  [bold]Each lens answers a different question.[/] Together they make one agent fast, careful and explainable.")

if __name__ == "__main__":
    a = sys.argv[1:] or ["scorecard"]; c = a[0]
    {"stream": cmd_stream, "quality": cmd_quality, "residency": cmd_residency, "govern": cmd_govern,
     "graphrag": cmd_graphrag, "scorecard": cmd_scorecard}.get(c, lambda: None)()
    if c == "decide": cmd_decide(a[a.index("--explain") + 1] if "--explain" in a else None)
    elif c == "ask": cmd_ask([int(x) for x in a[1:]] or list(QUESTIONS))
    elif c not in ("stream", "quality", "residency", "govern", "graphrag", "scorecard"): print(__doc__)
