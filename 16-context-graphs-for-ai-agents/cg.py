"""Context graph for an AI agent, hands-on (Kestrel Cold Chain, a fictional vaccine distributor).

A context graph links the business entities (products, lots, shipments, carriers, sites) with the
decision traces around them: what triggered each decision, which policy version applied, what evidence
was used, who proposed and approved it, which precedents it cited, what happened afterwards, and
whether it was later overturned. An agent queries that graph for context before it decides, and writes
its own decision back as a new trace.

Commands
  build                 load data/*.csv (+ agent write-backs) into a graph and save graph.json
  stats                 node and edge counts by type
  show ID               one node and its neighbours
  trace ID              the decision trace around a decision, as a tree
  context N             the context the graph retriever assembles for question N
  ask N --mode rag|graph  ask the local LLM question N with plain RAG or with the context graph
  compare               all questions, both modes, side by side
  writeback N           save the agent's graph-mode decision for N as a new (proposed) decision trace
  scorecard             score both modes
  export                write node and edge tables in the shape a Fabric graph model maps from
The model is a real LLM behind any OpenAI-compatible endpoint (default: local llama.cpp on port 8089).
"""
import argparse, csv, glob, json, math, os, re, sys, time, urllib.request
from collections import Counter, defaultdict
import networkx as nx, yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box
from rich.markup import escape

HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "data"); RUNS = os.path.join(HERE, "runs")
WB = os.path.join(D, "agent_decisions.jsonl")
BASE = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8089/v1"); MODEL = os.environ.get("LLM_MODEL", "qwen2.5-7b-instruct")
con = Console(width=int(os.environ.get("COLS", "140")), highlight=False)
Q = yaml.safe_load(open(os.path.join(HERE, "questions.yaml"))); TODAY = Q["today"]
MINT, RED, AMBER, DIM, SKY, VIO = "#34d399", "#f87171", "#fbbf24", "#94a3b8", "#38bdf8", "#a78bfa"
LABEL_COL = dict(Product=SKY, Lot=SKY, Shipment=SKY, Site=DIM, Carrier=SKY, Role=VIO, Excursion=AMBER, Policy=MINT, Decision=MINT, Outcome=AMBER, Document=DIM)

# ------------------------------------------------------------------ build
def rows(name): return list(csv.DictReader(open(os.path.join(D, name))))

def build_graph():
    G = nx.MultiDiGraph()
    def node(i, label, **p): G.add_node(i, label=label, **{k: v for k, v in p.items() if k != "id"})
    def edge(a, rel, b, **p):
        if a and b: G.add_edge(a, b, key=rel, rel=rel, **p)
    for r in rows("products.csv"): node(r["id"], "Product", **r)
    for r in rows("sites.csv"): node(r["id"], "Site", **r)
    for r in rows("carriers.csv"): node(r["id"], "Carrier", **r)
    for r in rows("roles.csv"): node(r["id"], "Role", **r)
    for r in rows("documents.csv"): node(r["id"], "Document", **r)
    for r in rows("lots.csv"): node(r["id"], "Lot", **r); edge(r["id"], "OF_PRODUCT", r["product"])
    for r in rows("shipments.csv"):
        node(r["id"], "Shipment", **r)
        edge(r["id"], "CARRIES", r["lot"]); edge(r["id"], "FROM", r["origin"]); edge(r["id"], "TO", r["destination"]); edge(r["id"], "BY_CARRIER", r["carrier"])
    for r in rows("excursions.csv"):
        node(r["id"], "Excursion", **r); edge(r["id"], "AFFECTED", r["lot"]); edge(r["id"], "ON_SHIPMENT", r["shipment"])
    pol = rows("policies.csv")
    for r in pol: node(r["id"], "Policy", **r)
    edge("SOP-TEMP-v3", "SUPERSEDES", "SOP-TEMP-v2", on="2026-04-01")
    decs = rows("decisions.csv")
    if os.path.exists(WB): decs += [json.loads(l) for l in open(WB) if l.strip()]
    for r in decs:
        node(r["id"], "Decision", **{k: v for k, v in r.items() if k not in ("cites", "evidence", "considered")})
        edge(r["id"], "TRIGGERED_BY", r["trigger"]); edge(r["id"], "ABOUT", r["about"]); edge(r["id"], "APPLIED", r["policy"])
        edge(r["id"], "PROPOSED_BY", r["proposed_by"]); edge(r["id"], "APPROVED_BY", r.get("approved_by") or None)
        for c in r.get("cites", []): edge(r["id"], "CITES", c)
        for c in r.get("evidence", []): edge(r["id"], "USED_EVIDENCE", c)
        for c in r.get("considered", []): edge(r["id"], "CONSIDERED", c)
    for r in rows("outcomes.csv"): node(r["id"], "Outcome", **r); edge(r["id"], "RESULT_OF", r["decision"])
    # decision-to-decision links recorded by QA
    edge("DEC-121", "OVERTURNS", "DEC-118", on="2026-05-20"); edge("DEC-131", "USED_EVIDENCE", "STAB-A")
    edge("DEC-138", "CITES", "DEC-131"); edge("DEC-142", "CITES", "DEC-135"); edge("DEC-142", "CITES", "DEC-131")
    edge("DEC-140", "CONSTRAINS", "CR-3", valid_to="2026-12-31")
    for x in ("EXC-2040", "EXC-2044"): edge("DEC-140", "USED_EVIDENCE", x)
    return G

def save(G): json.dump(nx.node_link_data(G, edges="links"), open(os.path.join(HERE, "graph.json"), "w"), indent=0)
def load():
    p = os.path.join(HERE, "graph.json")
    if not os.path.exists(p): G = build_graph(); save(G); return G
    return nx.node_link_graph(json.load(open(p)), directed=True, multigraph=True, edges="links")

TRACE_RELS = {"ABOUT", "CONSIDERED", "TRIGGERED_BY", "APPLIED", "PROPOSED_BY", "APPROVED_BY", "CITES", "USED_EVIDENCE", "RESULT_OF", "OVERTURNS", "CONSTRAINS", "SUPERSEDES"}

def cmd_build(a):
    t0 = time.time(); G = build_graph(); save(G)
    lab = Counter(d["label"] for _, d in G.nodes(data=True)); rel = Counter(d["rel"] for *_, d in G.edges(data=True))
    con.print(f"[bold {MINT}]context graph built[/]  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges in {1000*(time.time()-t0):.0f} ms  -> graph.json")
    ent = sum(v for k, v in lab.items() if k in ("Product", "Lot", "Shipment", "Site", "Carrier"))
    con.print(f"  entities {ent}   events {lab['Excursion']}   policies {lab['Policy']}   decisions {lab['Decision']}   outcomes {lab['Outcome']}")
    con.print(f"  decision-trace edges {sum(v for k, v in rel.items() if k in TRACE_RELS)} of {G.number_of_edges()}")

def cmd_stats(a):
    G = load(); lab = Counter(d["label"] for _, d in G.nodes(data=True)); rel = Counter(d["rel"] for *_, d in G.edges(data=True))
    t1 = Table(title="Nodes", box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}"); t1.add_column("label"); t1.add_column("count", justify="right")
    for k, v in sorted(lab.items(), key=lambda x: -x[1]): t1.add_row(f"[{LABEL_COL[k]}]{k}[/]", str(v))
    t2 = Table(title="Edges", box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}"); t2.add_column("relationship"); t2.add_column("count", justify="right"); t2.add_column("kind")
    for k, v in sorted(rel.items(), key=lambda x: -x[1]): t2.add_row(k, str(v), "[#34d399]decision trace[/]" if k in TRACE_RELS else "[#94a3b8]business fact[/]")
    g = Table.grid(padding=(0, 6)); g.add_row(t1, t2); con.print(g)

def fmt(G, n):
    d = G.nodes[n]; lab = d["label"]; c = LABEL_COL.get(lab, DIM)
    extra = {"Shipment": lambda: f"{d['product']} lot {d['lot']} via {d['carrier']} on {d['ship_date']}",
             "Excursion": lambda: f"{d['date']} {d['minutes']} min, max {d['max_c']} C, min {d['min_c']} C",
             "Decision": lambda: f"{d['date']} {d['disposition']} ({d['status']})",
             "Policy": lambda: f"{d['title']}, from {d['effective_from']}" + (f" to {d['effective_to']}" if d.get('effective_to') else ""),
             "Outcome": lambda: f"{d['date']} {d['result']}", "Role": lambda: d["role"], "Lot": lambda: f"{d['product']}, budget {d['stability_budget_min']} min",
             "Carrier": lambda: d["name"], "Product": lambda: d["name"], "Document": lambda: d["title"], "Site": lambda: f"{d['kind']}, {d['city']}"}
    return f"[bold {c}]{n}[/] [dim]{lab}[/]  {extra.get(lab, lambda: '')()}"

def cmd_show(a):
    G = load(); n = a.id; con.print(fmt(G, n))
    for _, b, d in G.out_edges(n, data=True): con.print(f"   --{d['rel']}--> {fmt(G, b)}")
    for b, _, d in G.in_edges(n, data=True): con.print(f"   <--{d['rel']}-- {fmt(G, b)}")

def cmd_trace(a):
    G = load(); root = a.id; t = Tree(fmt(G, root), guide_style=MINT)
    if G.nodes[root].get("rationale"): t.add(f"[italic]rationale:[/] {G.nodes[root]['rationale']}")
    for _, b, d in G.out_edges(root, data=True):
        br = t.add(f"[{AMBER}]{d['rel']}[/] -> {fmt(G, b)}")
        if d["rel"] in ("TRIGGERED_BY", "CITES", "CONSIDERED"):
            for _, c, d2 in G.out_edges(b, data=True):
                if d2["rel"] in ("AFFECTED", "ON_SHIPMENT", "OVERTURNS"): br.add(f"[{AMBER}]{d2['rel']}[/] -> {fmt(G, c)}")
            for c, _, d2 in G.in_edges(b, data=True):
                if d2["rel"] in ("OVERTURNS", "RESULT_OF"): br.add(f"[{RED if d2['rel']=='OVERTURNS' else AMBER}]{d2['rel']} by[/] <- {fmt(G, c)}")
    for b, _, d in G.in_edges(root, data=True):
        if d["rel"] in ("RESULT_OF", "OVERTURNS", "CITES"): t.add(f"[{RED if d['rel']=='OVERTURNS' else AMBER}]{d['rel']} by[/] <- {fmt(G, b)}")
    con.print(t)

# ------------------------------------------------------------------ graph retriever (the agent's tools)
def ids_in(text): return re.findall(r"\b(?:SH|L-[A-C]|DEC|EXC|OUT|CR|PRD)-[\w-]+|\bL-[A-C]-\d\d\b", text)

def policy_in_force(G, date):
    live = [n for n, d in G.nodes(data=True) if d["label"] == "Policy" and n.startswith("SOP") and d["effective_from"] <= date and (not d["effective_to"] or date <= d["effective_to"])]
    return live[0]

def lot_budget(G, lot):
    budget = int(G.nodes[lot]["stability_budget_min"]); used = []
    for e, _, d in G.in_edges(lot, data=True):
        if d["rel"] != "AFFECTED": continue
        for dec, _, d2 in G.in_edges(e, data=True):
            dd = G.nodes[dec]
            if d2["rel"] == "TRIGGERED_BY" and dd.get("status") == "final" and int(dd.get("deducts") or 0) > 0: used.append((dec, int(dd["deducts"])))
    return budget, used, budget - sum(m for _, m in used)

def decision_status(G, dec):
    over = [b for b, _, d in G.in_edges(dec, data=True) if d["rel"] == "OVERTURNS"]
    outs = [b for b, _, d in G.in_edges(dec, data=True) if d["rel"] == "RESULT_OF"]
    return over, outs

def precedents(G, product, froze, mentioned, mylot=None):
    """Past decisions on the same product family and the same kind of excursion (warm vs freeze), plus any the user mentioned."""
    out = []
    for n, d in G.nodes(data=True):
        if d["label"] != "Decision" or d.get("status") == "proposed": continue
        trig = d["trigger"]
        if not trig.startswith("EXC"): continue
        e = G.nodes[trig]; lot = e["lot"]; prod = G.nodes[lot]["product"]
        e_froze = float(e["min_c"]) <= 0
        same = (e_froze == froze) and (froze or prod == product) and d["policy"] != "SOP-TEMP-v2"
        named = d["about"] in mentioned
        if d["disposition"] not in ("RELEASE", "QUARANTINE", "DESTROY", "ESCALATE"): continue
        if named: out.append((0, "", n))
        elif same: out.append((1 if lot == mylot else 2, "~" + d["date"], n))
    out.sort(key=lambda x: x[1], reverse=True)
    out.sort(key=lambda x: (x[0], 0 if decision_status(G, x[2])[1] else 1))
    named = [n for r, _, n in out if r == 0]; rest = [n for r, _, n in out if r > 0][:3]
    return named + rest

def constraints(G, shipment, date):
    s = G.nodes[shipment]; res = []
    for target in (s["carrier"], s["lot"], s["product"], s["destination"]):
        for dec, _, d in G.in_edges(target, data=True):
            if d["rel"] == "CONSTRAINS" and date <= d.get("valid_to", "9999"): res.append((dec, target, d.get("valid_to")))
    return res

def graph_context(G, q):
    """Run the graph queries for a question and return (facts text, nodes used)."""
    used = set(); L = []
    ment = ids_in(q["text"]); ships = [m for m in ment if m.startswith("SH-")]
    if q["expect"] == "EXPLAIN":
        sh = ships[0]; decs = [b for b, _, d in G.in_edges(sh, data=True) if d["rel"] == "ABOUT"]
        for dec in decs:
            dd = G.nodes[dec]; used |= {dec, sh}
            L.append(f"- {dec} ({dd['date']}) decided {dd['disposition']} for {sh}. Rationale: {dd['rationale']}")
            for _, b, d in G.out_edges(dec, data=True):
                if d["rel"] == "ABOUT": continue
                used.add(b); L.append(f"- {dec} {d['rel']} {b}: " + re.sub(r"\[/?[^\]]*\]", "", fmt(G, b)).split("  ", 1)[-1])
            over, outs = decision_status(G, dec)
            for o in outs: used.add(o); L.append(f"- {o} RESULT_OF {dec}: {G.nodes[o]['result']}")
            for o in over: used.add(o); L.append(f"- {o} OVERTURNS {dec}")
        return "\n".join(L), used
    sh = ships[0]; s = G.nodes[sh]; lot = s["lot"]; prod = s["product"]; p = G.nodes[prod]
    exc = [e for e, _, d in G.in_edges(sh, data=True) if d["rel"] == "ON_SHIPMENT"][0]; e = G.nodes[exc]; used |= {sh, lot, prod, exc}
    froze = float(e["min_c"]) <= 0
    L.append(f"- Shipment {sh}: {p['name']} ({prod}, freeze-sensitive: {p['freeze_sensitive']}), lot {lot}, carrier {s['carrier']} {G.nodes[s['carrier']]['name']}.")
    L.append(f"- Excursion {exc} on {e['date']}: {e['minutes']} min, max {e['max_c']} C, min {e['min_c']} C.")
    pol = policy_in_force(G, e["date"]); used.add(pol)
    sup = [b for _, b, d in G.out_edges(pol, data=True) if d["rel"] == "SUPERSEDES"]
    L.append(f"- Policy in force on {e['date']}: {pol}" + (f" (it SUPERSEDES {', '.join(sup)}, which no longer applies)" if sup else "") + f". Rule: {G.nodes[pol]['rule']}")
    budget, spent, left = lot_budget(G, lot); used |= {x for x, _ in spent}
    L.append(f"- Lot {lot} stability budget: {budget} min. Already used: " + (", ".join(f"{m} min by {x}" for x, m in spent) or "none") + f". Left BEFORE this excursion: {left} min (Step 2 needs 60).")
    for dec in precedents(G, prod, froze, set(ment), lot):
        dd = G.nodes[dec]; over, outs = decision_status(G, dec); used.add(dec)
        st = f"OVERTURNED by {', '.join(over)}" if over else "still valid"
        oc = "; ".join(f"{o}: {G.nodes[o]['result']}" for o in outs)
        L.append(f"- Precedent {dec} ({dd['date']}, about {dd['about']}): {dd['disposition']}, {st}." + (f" Outcome {oc}" if oc else ""))
        for o in over: used.add(o); L.append(f"  - {o} ({G.nodes[o]['date']}): {G.nodes[o]['rationale']}")
    used.add("POL-SIGNOFF-01"); L.append(f"- POL-SIGNOFF-01: {G.nodes['POL-SIGNOFF-01']['rule']}")
    # the checks the policy in force asks for, answered from the graph
    yn = lambda b: "yes" if b else "no"
    fs = p["freeze_sensitive"] == "yes"; mx = float(e["max_c"]); mins = int(e["minutes"])
    cons = constraints(G, sh, TODAY); bad = [x for x in precedents(G, prod, froze, set(ment), lot) if decision_status(G, x)[0]]
    s2 = mx <= 12 and mins <= 30 and left >= 60
    why2 = ", ".join(x for x, ok in ((f"max {mx} C > 12.0", mx <= 12), (f"{mins} min > 30", mins <= 30), (f"only {left} min budget left < 60", left >= 60)) if not ok)
    L.append(f"- {pol} checks answered from the graph: Step 1 condition (freeze-sensitive AND froze): {yn(fs and froze)}. "
             f"Step 2 condition (max <= 12 C, <= 30 min, >= 60 min budget left): {yn(s2)}" + (f" ({why2})" if why2 else "") + ". "
             f"Overturned precedents to ignore: {', '.join(bad) or 'none'}. Active constraints: {', '.join(c[0] for c in cons) or 'none'}.")
    for dec, target, vt in constraints(G, sh, TODAY):
        used.add(dec); L.append(f"- Active constraint {dec} on {target} (valid to {vt}), OVERRIDES the policy result: {G.nodes[dec]['rationale']}")
    return "\n".join(L), used

# ------------------------------------------------------------------ plain RAG baseline (BM25 over the same knowledge as text)
def tok(t): return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", t.lower())
def rag_context(q, k=4):
    docs = {os.path.basename(p): open(p).read() for p in sorted(glob.glob(os.path.join(HERE, "docs_corpus", "*.md")))}
    T = {n: tok(t) for n, t in docs.items()}; N = len(T); avg = sum(map(len, T.values())) / N
    df = Counter(w for ws in T.values() for w in set(ws)); qs = tok(q["text"])
    def bm25(ws):
        tf = Counter(ws); s = 0.0
        for w in qs:
            if w in tf: s += math.log(1 + (N - df[w] + .5) / (df[w] + .5)) * tf[w] * 2.2 / (tf[w] + 1.2 * (.25 + .75 * len(ws) / avg))
        return s
    top = sorted(T, key=lambda n: -bm25(T[n]))[:k]
    return "\n\n".join(f"[{n}]\n{docs[n].strip()}" for n in top), top

# ------------------------------------------------------------------ LLM
SYSTEM = ("You are the release agent of a vaccine cold-chain distributor. Use ONLY the context provided. "
          "For a shipment, choose exactly one disposition: RELEASE, QUARANTINE, DESTROY or ESCALATE. "
          "DESTROY is only for a freeze-sensitive product that froze; a failed release check means QUARANTINE. Apply the policy that is in force, check the lot's remaining stability budget, never rely on a precedent that was overturned, "
          "and obey any active constraint, which overrides the policy. "
          'Reply with JSON only: {"disposition": "...", "cites": ["IDs you relied on"], "reason": "one or two sentences that name the deciding fact with its numbers or IDs"}')

SYSTEM_WHY = ("You explain past decisions of a vaccine cold-chain distributor. Use ONLY the context provided. "
              'Reply with JSON only: {"disposition": "EXPLAIN", "cites": ["every ID from the context that explains the decision: the decision, '
              'its trigger, the policy, the evidence, the approver and the outcome"], "reason": "two sentences: why it was decided, and how it turned out"}')

def llm(user, why=False):
    body = json.dumps(dict(model=MODEL, temperature=0, seed=42, max_tokens=300, cache_prompt=False, response_format={"type": "json_object"},
                           messages=[dict(role="system", content=SYSTEM_WHY if why else SYSTEM), dict(role="user", content=user)])).encode()
    rq = urllib.request.Request(BASE + "/chat/completions", body, {"Content-Type": "application/json", "Authorization": "Bearer local"})
    t0 = time.time(); r = json.load(urllib.request.urlopen(rq, timeout=600))
    return r["choices"][0]["message"]["content"], time.time() - t0, r.get("usage", {})

def parse(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    try: j = json.loads(m.group(0))
    except Exception: j = dict(disposition="?", cites=[], reason=txt.strip()[:200])
    j["disposition"] = str(j.get("disposition", "?")).upper().split()[0] if j.get("disposition") else "?"
    j["cites"] = [str(c) for c in j.get("cites", [])]
    return j

def grade(q, j):
    if q["expect"] == "EXPLAIN":
        hits = [c for c in q["cite_pool"] if any(c in x for x in j["cites"]) or c in j.get("reason", "")]
        return len(hits) >= q["cite_min"], f"{len(hits)} of {len(q['cite_pool'])} trace nodes"
    ok = j["disposition"] == q["expect"]
    return ok, ("" if ok else f"expected {q['expect']}")

def getq(n): return next(q for q in Q["questions"] if q["id"] == int(n))

def ask(n, mode, quiet=False):
    q = getq(n); G = load()
    ctx, used = (graph_context(G, q) if mode == "graph" else rag_context(q))
    user = f"Today is {TODAY}.\n\nCONTEXT ({'context graph query results' if mode == 'graph' else 'top retrieved documents'}):\n{ctx}\n\nQUESTION: {q['text']}"
    raw, secs, usage = llm(user, why=q["expect"] == "EXPLAIN"); j = parse(raw); ok, note = grade(q, j)
    rec = dict(q=q["id"], mode=mode, question=q["text"], context=ctx, used=sorted(used), answer=j, raw=raw, ok=ok, note=note, seconds=round(secs, 1), prompt_tokens=usage.get("prompt_tokens"))
    os.makedirs(RUNS, exist_ok=True); json.dump(rec, open(os.path.join(RUNS, f"{mode}_Q{q['id']}.json"), "w"), indent=1)
    if not quiet: show_run(rec)
    return rec

def show_run(r):
    col = MINT if r["mode"] == "graph" else AMBER
    con.print(Panel(r["question"], title=f"Q{r['q']}  [{col}]{r['mode'].upper()}[/]", border_style=col, width=130))
    con.print(f"[bold]{'graph queries returned' if r['mode']=='graph' else 'retrieved documents'}:[/]")
    for line in r["context"].splitlines():
        if r["mode"] == "rag":
            if line.startswith("["): con.print(f"  [bold {AMBER}]{escape(line)}[/]")
            elif line.strip(): con.print(f"    [{DIM}]{escape(line)}[/]")
        elif r["mode"] == "graph": con.print("  " + re.sub(r"\b((?:SOP|POL)-[\w-]+|DEC-\d+|OUT-\d+)\b", rf"[{MINT}]\1[/]", line.replace("[", "\\[")).replace("OVERTURNED", f"[{RED}]OVERTURNED[/]").replace("SUPERSEDES", f"[{AMBER}]SUPERSEDES[/]"))
    a = r["answer"]; v = f"[bold {MINT}]correct[/]" if r["ok"] else f"[bold {RED}]wrong[/] [dim]{r['note']}[/]"
    con.print(f"\n[bold]agent ->[/] [bold white on #1e293b] {a['disposition']} [/]  {v}   [dim]{r['seconds']} s, {r['prompt_tokens']} prompt tokens[/]")
    con.print(f"  [dim]reason:[/] {a.get('reason','')}")
    con.print(f"  [dim]cites:[/]  {', '.join(a['cites']) or '-'}")

def cmd_context(a):
    q = getq(a.n); G = load(); ctx, used = graph_context(G, q)
    con.print(Panel(q["text"], title=f"Q{q['id']}  context from the graph", border_style=MINT, width=130))
    for line in ctx.splitlines(): con.print("  " + re.sub(r"\b((?:SOP|POL)-[\w-]+|DEC-\d+|OUT-\d+)\b", rf"[{MINT}]\1[/]", line.replace("[", "\\[")).replace("OVERTURNED", f"[{RED}]OVERTURNED[/]").replace("SUPERSEDES", f"[{AMBER}]SUPERSEDES[/]"))
    con.print(f"\n[dim]{len(used)} graph nodes in the context pack, {len(ctx.split())} words[/]")

def cmd_ask(a):
    if a.cached: show_run(json.load(open(os.path.join(RUNS, f"{a.mode}_Q{a.n}.json"))))
    else: ask(a.n, a.mode)

def load_runs():
    R = {}
    for p in glob.glob(os.path.join(RUNS, "*_Q*.json")):
        r = json.load(open(p)); R[(r["mode"], r["q"])] = r
    return R

def cmd_compare(a):
    R = load_runs(); t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}", width=136)
    t.add_column("Q", justify="right"); t.add_column("case", width=46); t.add_column("expected"); t.add_column("plain RAG"); t.add_column("context graph")
    for q in Q["questions"]:
        cell = lambda m: (lambda r: f"[{MINT if r['ok'] else RED}]{r['answer']['disposition']} {'✓' if r['ok'] else '✗'}[/]")(R[(m, q["id"])]) if (m, q["id"]) in R else "-"
        t.add_row(str(q["id"]), q["why"][:46] + "…", q["expect"], cell("rag"), cell("graph"))
    con.print(t)

def cmd_scorecard(a):
    R = load_runs(); t = Table(title="Scorecard: same local model, same questions", box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}")
    for c in ("", "plain RAG", "context graph"): t.add_column(c, justify="right" if c else "left")
    sc = {m: sum(R[(m, q["id"])]["ok"] for q in Q["questions"] if (m, q["id"]) in R) for m in ("rag", "graph")}
    n = len(Q["questions"])
    t.add_row("correct decisions", f"[{RED}]{sc['rag']}/{n}[/]", f"[{MINT}]{sc['graph']}/{n}[/]")
    for label, key in (("avg prompt tokens", "prompt_tokens"), ("avg seconds", "seconds")):
        avg = lambda m: sum((R[(m, q['id'])][key] or 0) for q in Q['questions']) / n
        t.add_row(label, f"{avg('rag'):.0f}" if key == "prompt_tokens" else f"{avg('rag'):.1f}", f"{avg('graph'):.0f}" if key == "prompt_tokens" else f"{avg('graph'):.1f}")
    trace = lambda m: sum(1 for q in Q["questions"] if (m, q["id"]) in R and any(c.startswith(("DEC", "OUT")) for c in R[(m, q["id"])]["answer"]["cites"]))
    t.add_row("answers citing a decision trace", str(trace("rag")), str(trace("graph")))
    stale = lambda m: sum(1 for q in Q["questions"] if (m, q["id"]) in R and any(re.search(r"dec-118|v2", c, re.I) for c in R[(m, q["id"])]["answer"]["cites"]))
    t.add_row("relied on a superseded policy or overturned decision", f"[{RED}]{stale('rag')}[/]", f"[{MINT}]{stale('graph')}[/]")
    con.print(t)

def cmd_writeback(a):
    r = json.load(open(os.path.join(RUNS, f"graph_Q{a.n}.json"))); q = getq(a.n); G = load()
    sh = ids_in(q["text"])[0]; exc = [e for e, _, d in G.in_edges(sh, data=True) if d["rel"] == "ON_SHIPMENT"][0]
    pol = policy_in_force(G, G.nodes[exc]["date"])
    rec = dict(id=f"DEC-A{sh[3:]}", date=TODAY, about=sh, trigger=exc, policy=pol, disposition=r["answer"]["disposition"], proposed_by="AGENT-1", approved_by="",
               rationale=r["answer"].get("reason", ""), status="proposed", deducts=0,
               cites=[c for c in r["answer"]["cites"] if c.startswith("DEC-")],
               considered=[c for c in r["used"] if c.startswith("DEC-") and c not in r["answer"]["cites"]], evidence=[c for c in r["used"] if c.startswith("OUT-")])
    lines = [l for l in open(WB)] if os.path.exists(WB) else []
    lines = [l for l in lines if json.loads(l)["id"] != rec["id"]] + [json.dumps(rec) + "\n"]
    open(WB, "w").writelines(lines); G = build_graph(); save(G)
    con.print(f"[bold {MINT}]wrote decision trace {rec['id']}[/] (status: proposed, waiting for a QA reviewer per POL-SIGNOFF-01)")
    con.print(f"  graph now {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    a.id = rec["id"]; cmd_trace(a)

def cmd_export(a):
    G = load(); out = os.path.join(D, "fabric"); os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*.csv")): os.remove(f)
    by = defaultdict(list)
    for n, d in G.nodes(data=True): by[d["label"]].append({"id": n, **{k: v for k, v in d.items() if k != "label"}})
    for lab, rs in by.items():
        keys = sorted({k for r in rs for k in r}, key=lambda k: (k != "id", k))
        with open(os.path.join(out, f"node_{lab.lower()}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rs)
    eb = defaultdict(list)
    for a_, b, d in G.edges(data=True): eb[(d["rel"], G.nodes[a_]["label"], G.nodes[b]["label"])].append(dict(src_id=a_, dst_id=b, **{k: v for k, v in d.items() if k != "rel"}))
    for (rel, la, lb), rs in sorted(eb.items()):
        keys = sorted({k for r in rs for k in r}, key=lambda k: (k not in ("src_id", "dst_id"), k))
        with open(os.path.join(out, f"edge_{rel.lower()}__{la.lower()}_{lb.lower()}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rs)
    con.print(f"[bold {MINT}]exported[/] {len(by)} node tables and {len(eb)} edge tables to data/fabric/  (one table per node type and per edge type)")
    for f in sorted(os.listdir(out))[:8]: con.print(f"  {f}")
    con.print(f"  … {len(os.listdir(out)) - 8} more. Load them into a lakehouse and map them in a Fabric graph model; see gql/ for the matching queries.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("build", "stats", "compare", "scorecard", "export"): sp.add_parser(c)
    for c in ("show", "trace"): sp.add_parser(c).add_argument("id")
    for c in ("context", "writeback"): sp.add_parser(c).add_argument("n")
    p = sp.add_parser("ask"); p.add_argument("n"); p.add_argument("--mode", choices=["rag", "graph"], default="graph"); p.add_argument("--cached", action="store_true")
    a = ap.parse_args(); globals()["cmd_" + a.cmd](a)
