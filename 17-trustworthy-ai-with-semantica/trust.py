"""Lesson 17: an accountable claims-triage agent on Semantica (fictional Cedarline Home Insurance).

  python trust.py build                      # provenance store + context graph + policy versions
  python trust.py facts CLM-2603             # every fact with its source, section, quote and checksum
  python trust.py conflicts                  # Semantica ConflictDetector over all claims
  python trust.py rules CLM-2602             # Semantica Reasoner: route + plain-English explanation
  python trust.py ask 2 --mode rag|semantica # local LLM decides; semantica mode writes an audit record
  python trust.py audit [CLM-.. | DEC-..]    # replay a decision: lineage, hash chain, prompt hash
  python trust.py tamper                     # edit a copy of the store and watch the chain break
  python trust.py compare | scorecard        # side by side, and the score
  python trust.py export                     # PROV-O Turtle + flat CSV tables (OneLake-ready)
"""
import csv, hashlib, json, os, re, shutil, sqlite3, sys, time, urllib.request, warnings, logging, datetime as dt, pathlib
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false"); os.environ["SEMANTICA_DISABLE_PROGRESS"] = "1"
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
H = pathlib.Path(__file__).parent; os.chdir(H)
RUNS = H / "runs"; RUNS.mkdir(exist_ok=True); DB = RUNS / "provenance.db"
BASE = os.environ.get("LLM_BASE", "http://127.0.0.1:8089/v1"); MODEL = os.environ.get("LLM_MODEL", "qwen2.5-7b-instruct-q4_k_m")
TODAY = "2026-10-20"  # triage date for this lesson
con = Console(width=int(os.environ.get("COLS", "120")), highlight=False)
MINT, AMBER, RED, DIM = "#34D399", "#FBBF24", "#F87171", "#94A3B8"

def _q():
    import contextlib, io
    return contextlib.redirect_stderr(io.StringIO())
with _q():
    from semantica.provenance import ProvenanceManager, verify_checksum
    from semantica.provenance.storage import SQLiteStorage
    from semantica.conflicts import ConflictDetector, ConflictResolver
    from semantica.context import ContextGraph, PolicyEngine
    from semantica.context.decision_models import Policy
    from semantica.reasoning import Reasoner, ExplanationGenerator

def rows(name): return list(csv.DictReader(open(H / "data" / f"{name}.csv")))
def sha(b): return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()
def sections(doc):
    """Split a document into citable chunks: DOC#4.2 for numbered sections, DOC for one-paragraph claim documents."""
    txt = (H / "docs_corpus" / f"{doc}.md").read_text(); parts = re.split(r"^## ", txt, flags=re.M)
    if len(parts) == 1: return {doc: txt.split("\n", 1)[1].strip()}
    out = {}
    for p in parts[1:]:
        head, body = p.split("\n", 1); num = head.split()[0]
        out[f"{doc}#{num}" if re.match(r"\d", num) else f"{doc}#{head.lower()}"] = f"{head}. {body.strip()}"
    return out

CLAUSES = {"WORD-2025": ("2025-01-01", "2026-06-01"), "WORD-2026": ("2026-06-01", None)}
GUIDE = {"GL-TRIAGE-v2": dict(version="2", fast_max=25000, std_max=50000, valid=("2026-01-15", "2026-09-01")),
         "GL-TRIAGE-v3": dict(version="3", fast_max=10000, std_max=50000, valid=("2026-09-01", None))}
def pm(): return ProvenanceManager(storage_path=str(DB))

# ---------------------------------------------------------------- build
def build_graph():
    """Context graph: claims, facts, source documents, policy clauses with validity windows. Deterministic, rebuilt on load."""
    g = ContextGraph()
    src = {s["doc_id"]: s for s in rows("sources")}
    for d, s in src.items():
        g.add_node(d, "SourceDocument", content=d, kind=s["kind"], credibility=float(s["credibility"]))
    for d, (vf, vu) in CLAUSES.items():
        for cid, text in sections(d).items():
            kw = dict(valid_from=vf, **({"valid_until": vu} if vu else {}))
            g.add_node(cid, "PolicyClause", content=text, source=d, **kw); g.add_edge(cid, d, "stated_in")
    for p in rows("policies"):
        g.add_node(p["claim_id"], "Claim", content=p["claim_id"], policy_id=p["policy_id"], policy_start=p["start_date"])
    for f in rows("facts"):
        g.add_node(f["fact_id"], "Fact", content=f"{f['property']}={f['value']}", claim=f["claim_id"], property=f["property"],
                   value=f["value"], source=f["source_doc"], quote=f["quote"])
        g.add_edge(f["claim_id"], f["fact_id"], "has_fact"); g.add_edge(f["fact_id"], f["source_doc"], "extracted_from")
    pe = PolicyEngine(g); now = dt.datetime(2026, 1, 15)
    v2 = GUIDE["GL-TRIAGE-v2"]; v3 = GUIDE["GL-TRIAGE-v3"]
    pe.add_policy(Policy(policy_id="GL-TRIAGE", name="Claims triage guideline", description="Routing thresholds",
                         rules=dict(fast_max=v2["fast_max"], std_max=v2["std_max"]), category="claim_triage", version="2",
                         created_at=now, updated_at=now))
    pe.update_policy("GL-TRIAGE", dict(fast_max=v3["fast_max"], std_max=v3["std_max"], refer_on_conflict=True),
                     "Lower fast-track limit to $10,000; refer conflicting facts to an adjuster", "3")
    return g, pe

def build():
    if DB.exists(): DB.unlink()
    for f in RUNS.glob("*.json"): f.unlink()
    m = pm(); src = {s["doc_id"]: s for s in rows("sources")}; n = 0
    for d, s in src.items():   # 1) every source document, fingerprinted
        body = (H / "docs_corpus" / f"{d}.md").read_bytes()
        m.track_entity(d, source=f"docs_corpus/{d}.md", entity_type="SourceDocument", confidence=float(s["credibility"]),
                       metadata=dict(kind=s["kind"], sha256=sha(body)), valid_from=s["valid_from"] or None, valid_until=s["valid_until"] or None); n += 1
        for cid, text in (sections(d).items() if d in CLAUSES or d.startswith("GL-") else []):
            vf, vu = (CLAUSES[d] if d in CLAUSES else GUIDE[d]["valid"])
            m.track_entity(cid, source=d, entity_type="PolicyClause", source_quote=text[:120], valid_from=vf, valid_until=vu); n += 1
    for f in rows("facts"):   # 2) every extracted fact, pointing at document + section + exact quote
        m.track_entity(f["fact_id"], source=f["source_doc"], entity_type="Fact", source_location=f["location"], source_quote=f["quote"],
                       confidence=float(src[f["source_doc"]]["credibility"]),
                       metadata=dict(claim=f["claim_id"], property=f["property"], value=f["value"]), agent_id="fact-extractor"); n += 1
    g, pe = build_graph()
    st = m.get_statistics(); ch = m.verify_chain()
    t = Table(title="Semantica build", box=box.SIMPLE_HEAVY, title_style=f"bold {MINT}")
    t.add_column("Store"); t.add_column("What", style=DIM); t.add_column("Count", justify="right", style=MINT)
    t.add_row("Provenance (SQLite)", "source documents", str(st["entity_types"].get("SourceDocument", 0)))
    t.add_row("", "policy and guideline clauses", str(st["entity_types"].get("PolicyClause", 0)))
    t.add_row("", "extracted facts (doc + section + quote)", str(st["entity_types"].get("Fact", 0)))
    t.add_row("Context graph", "nodes / edges", f"{len(g.find_nodes(limit=10000))} / {len(g.find_edges(limit=10000))}")
    t.add_row("Policy engine", "GL-TRIAGE versions", " -> ".join("v" + p.version for p in pe.get_policy_history("GL-TRIAGE")))
    t.add_row("Hash chain", "entries, valid", f"{ch['total_entries']}, {ch['valid']}")
    con.print(t)

# ---------------------------------------------------------------- facts / conflicts / rules
def claim_facts(c): return [f for f in rows("facts") if f["claim_id"] == c]
def cred(): return {s["doc_id"]: float(s["credibility"]) for s in rows("sources")}

def facts(c):
    m = pm(); t = Table(title=f"Facts for {c}, each with its source", box=box.SIMPLE_HEAVY, title_style=f"bold {MINT}")
    for col in ["Fact", "Property", "Value", "Source", "Exact quote", "Conf", "Checksum", "Grounded"]: t.add_column(col)
    for f in claim_facts(c):
        e = m.storage.retrieve(f["fact_id"])
        t.add_row(f["fact_id"], f["property"], f["value"], f"{e.source_document} ({e.source_location})", f'"{e.source_quote}"',
                  f"{e.confidence:.1f}", f"[{MINT}]{e.checksum[:10]}[/] {'ok' if verify_checksum(e) else 'BAD'}", "yes" if grounded(e) else f"[{RED}]no[/]")
    con.print(t)

def detect(c):
    """Semantica ConflictDetector over the facts of one claim; expert_review for material facts."""
    cr = cred(); ents = [dict(id=c, type="Claim", **{f["property"]: f["value"]}, source=f["source_doc"], confidence=cr[f["source_doc"]],
                             fact_id=f["fact_id"]) for f in claim_facts(c)]
    d = ConflictDetector(); res = ConflictResolver(); out = []
    for p in ("date_of_loss", "cause", "amount"):
        for k in d.detect_value_conflicts([e for e in ents if p in e], p):
            weighted = res.resolve_conflict(k, "credibility_weighted"); review = res.resolve_conflict(k, "expert_review")
            fids = {e["source"]: e["fact_id"] for e in ents if p in e}
            out.append(dict(property=p, values=k.conflicting_values, sources=[s["document"] for s in k.sources],
                            facts=[fids[s["document"]] for s in k.sources], severity=k.severity,
                            weighted_pick=weighted.resolved_value, expert_review=review.metadata.get("requires_expert_review", False)))
    return out

def conflicts(c=None):
    t = Table(title="Semantica ConflictDetector", box=box.SIMPLE_HEAVY, title_style=f"bold {MINT}")
    for col in ["Claim", "Property", "Source A", "Source B", "Credibility pick", "Action"]: t.add_column(col)
    for cl in [c] if c else [p["claim_id"] for p in rows("policies")]:
        ks = detect(cl)
        if not ks: t.add_row(cl, f"[{DIM}]-[/]", f"[{DIM}]no conflicts[/]", "", "", f"[{MINT}]ok[/]")
        for k in ks:
            a, b = [f"{v} ({s})" for v, s in zip(k["values"], k["sources"])]
            t.add_row(cl, k["property"], a, b, f"[{DIM}]{k['weighted_pick']}[/]", f"[{AMBER}]expert review[/]")
    con.print(t)

def in_force(dol):
    g, _ = build_graph(); at = dt.datetime.fromisoformat(dol)
    return {n["id"]: n for n in g.find_active_nodes("PolicyClause", at_time=at)}

def evaluate(c):
    """Turns the graph into reasoner facts, runs Semantica's forward chaining, returns route + explanation + evidence."""
    fs = claim_facts(c); pol = next(p for p in rows("policies") if p["claim_id"] == c); ks = detect(c)
    g, pe = build_graph(); cur = pe.get_policy("GL-TRIAGE"); rules = cur.rules
    val = lambda p: sorted({f["value"] for f in fs if f["property"] == p})
    r = Reasoner(); facts_in = []; ev = {}
    def add(s, why): r.add_fact(s); facts_in.append(s); ev[s] = why
    for k in ks: add(f"Conflict({c}, {k['property']})", k["facts"])
    if not ks:
        add(f"Consistent({c})", [f["fact_id"] for f in fs])
        dol = val("date_of_loss")[0]; cause = val("cause")[0]; amt = float(val("amount")[0])
        add(f"Cause({c}, {cause})", [f["fact_id"] for f in fs if f["property"] == "cause"])
        clauses = in_force(dol); c42 = next(i for i in clauses if i.endswith("#4.2"))
        add(f"InForce({c}, {c42.split('#')[0].replace('-', '_')}_4_2)", [c42])
        if dol < pol["start_date"]: add(f"StartedBeforePolicy({c})", [f["fact_id"] for f in fs if f["property"] == "date_of_loss"])
        band = "Low" if amt <= rules["fast_max"] else ("Mid" if amt <= rules["std_max"] else "High")
        add(f"Band({c}, {band})", [f["fact_id"] for f in fs if f["property"] == "amount"] + [f"GL-TRIAGE-v{cur.version}"])
    for rule in ["IF Conflict(?c, ?p) THEN Route(?c, REFER_ADJUSTER)",
                 "IF Cause(?c, sudden_escape) THEN Covered(?c)",
                 "IF Cause(?c, sewer_backup) AND InForce(?c, WORD_2026_4_2) THEN Covered(?c)",
                 "IF Cause(?c, sewer_backup) AND InForce(?c, WORD_2025_4_2) THEN Excluded(?c)",
                 "IF Cause(?c, gradual_seepage) THEN Excluded(?c)",
                 "IF StartedBeforePolicy(?c) THEN Excluded(?c)",
                 "IF Excluded(?c) AND Consistent(?c) THEN Route(?c, DENY)",
                 "IF Covered(?c) AND Band(?c, Low) AND Consistent(?c) THEN Route(?c, FAST_TRACK)",
                 "IF Covered(?c) AND Band(?c, Mid) AND Consistent(?c) THEN Route(?c, STANDARD_REVIEW)",
                 "IF Band(?c, High) AND Consistent(?c) THEN Route(?c, SENIOR_REVIEW)"]: r.add_rule(rule)
    with _q(): res = r.forward_chain()
    order = ["REFER_ADJUSTER", "DENY", "SENIOR_REVIEW", "STANDARD_REVIEW", "FAST_TRACK"]
    routes = [x for x in res if x.conclusion.startswith("Route(")]
    best = min(routes, key=lambda x: order.index(x.conclusion.split(", ")[1].rstrip(")")))
    route = best.conclusion.split(", ")[1].rstrip(")")
    eg = ExplanationGenerator(); chain = [x for x in res if x.conclusion in best.premises] + [best]
    expl = [eg.generate_explanation(x).natural_language for x in chain]
    return dict(claim=c, policy=pol, route=route, conflicts=ks, inputs=facts_in, evidence=ev, explanation=expl,
                guideline=f"GL-TRIAGE-v{cur.version}", rules=rules, derived=[x.conclusion for x in res])

def show_rules(c):
    e = evaluate(c)
    con.print(Panel("\n".join(f"[{DIM}]fact[/] {s}" for s in e["inputs"]), title=f"Reasoner input for {c}", border_style=DIM, width=110))
    for line in e["explanation"]: con.print(f"[{MINT}]>[/] {line}")
    con.print(f"\nRoute: [bold {MINT}]{e['route']}[/]  (guideline {e['guideline']}, fast-track up to ${e['rules']['fast_max']:,})")

# ---------------------------------------------------------------- the agent
SCHEMA = ('Return JSON only: {"route": one of FAST_TRACK, STANDARD_REVIEW, SENIOR_REVIEW, REFER_ADJUSTER, DENY, '
          '"rationale": "two sentences", "cited": [ids of the sources you used], '
          '"conflicts": [{"property": "date_of_loss|cause|amount", "values": [..]}] or []}')
SYS_RAG = "You are a home-insurance claims triage assistant. Decide the route for the claim using only the retrieved context. " + SCHEMA
SYS_SEM = ("You are an accountable home-insurance claims triage assistant. Use only the evidence pack. Cite fact ids (F..) and clause ids "
           "for every statement. If the pack lists a conflict, you must report it and must not auto-decide. " + SCHEMA)
Q = {1: "CLM-2601", 2: "CLM-2602", 3: "CLM-2603", 4: "CLM-2604", 5: "CLM-2605"}
EXPECT = {"CLM-2601": ("FAST_TRACK", None), "CLM-2602": ("FAST_TRACK", None), "CLM-2603": ("REFER_ADJUSTER", "date_of_loss"),
          "CLM-2604": ("REFER_ADJUSTER", "cause"), "CLM-2605": ("STANDARD_REVIEW", None)}

def corpus():
    out = {}
    for f in sorted((H / "docs_corpus").glob("*.md")): out.update(sections(f.stem))
    return out
def retrieve(query, k=6, kinds=None):
    from sklearn.feature_extraction.text import TfidfVectorizer
    ids, texts = zip(*[(i, t) for i, t in corpus().items() if not kinds or i.startswith(kinds)]); v = TfidfVectorizer(stop_words="english").fit(texts + (query,))
    import numpy as np
    s = (v.transform(texts) @ v.transform([query]).T).toarray().ravel(); top = np.argsort(-s)[:k]
    return [(ids[i], texts[i], float(s[i])) for i in top]

def llm(system, user):
    body = json.dumps(dict(model=MODEL, temperature=0, seed=42, max_tokens=320, cache_prompt=False, response_format={"type": "json_object"},
                           messages=[dict(role="system", content=system), dict(role="user", content=user)])).encode()
    rq = urllib.request.Request(BASE + "/chat/completions", body, {"Content-Type": "application/json", "Authorization": "Bearer local"})
    t0 = time.time(); r = json.load(urllib.request.urlopen(rq, timeout=900))
    return r["choices"][0]["message"]["content"], round(time.time() - t0, 1), r.get("usage", {})

def parse(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    try: j = json.loads(m.group(0))
    except Exception: j = dict(route="?", rationale=txt.strip()[:200], cited=[], conflicts=[])
    j["route"] = str(j.get("route", "?")).upper().strip(); j["cited"] = [str(x) for x in j.get("cited") or []]
    j["conflicts"] = [x for x in (j.get("conflicts") or []) if isinstance(x, dict)]
    return j

def pack(c):
    e = evaluate(c); fs = claim_facts(c); cr = cred(); pol = e["policy"]
    L = [f"CLAIM {c}, policy {pol['policy_id']}, policy start {pol['start_date']}, triage date {TODAY}.", "FACTS (id, value, source, quote, credibility):"]
    L += [f"- {f['fact_id']} {f['property']} = {f['value']} | {f['source_doc']} ({f['location']}) \"{f['quote']}\" | {cr[f['source_doc']]}" for f in fs]
    L.append("CONFLICTS (Semantica ConflictDetector): " + ("none" if not e["conflicts"] else ""))
    L += [f"- {k['property']}: " + " vs ".join(f"{v} ({fid}, {s})" for v, fid, s in zip(k["values"], k["facts"], k["sources"])) + " -> expert review"
          for k in e["conflicts"]]
    dols = sorted({f["value"] for f in fs if f["property"] == "date_of_loss"})
    L.append(f"CLAUSES IN FORCE ON THE DATE OF LOSS {dols[0]} (temporal validity):")
    L += [f"- {cid}: {n['content'][:150]}" for cid, n in in_force(dols[0]).items()]
    L.append(f"GUIDELINE IN FORCE: {e['guideline']} (v2 superseded 2026-09-01): " + sections(e["guideline"]).get(f"{e['guideline']}#routing", "")[:520])
    L.append(f"RULE CHECK (Semantica Reasoner): route {e['route']}. " + " ".join(e["explanation"]))
    return "\n".join(L), e

def valid_citation(cid, dol, m):
    ent = m.storage.retrieve(cid)
    if cid.startswith("GL-"): dol = TODAY   # guidelines apply on the triage date, policy wording on the date of loss
    if ent is None: return False, "not in the provenance store"
    if ent.valid_until and dol >= ent.valid_until: return False, f"not in force on {dol}"
    if ent.valid_from and dol < ent.valid_from: return False, f"not yet in force on {dol}"
    return True, ""

def grade(c, j, m):
    exp, kprop = EXPECT[c]; dol = min(f["value"] for f in claim_facts(c) if f["property"] == "date_of_loss")
    route_ok = j["route"] == exp
    bad = [(x, why) for x in j["cited"] for ok, why in [valid_citation(x.split(" ")[0].strip(), dol, m)] if not ok]
    cite_ok = bool(j["cited"]) and not bad
    props = {str(x.get("property", "")).lower() for x in j["conflicts"]}
    conf_ok = (props == {kprop}) if kprop else not props
    return dict(route_ok=route_ok, cite_ok=cite_ok, conf_ok=conf_ok, bad_cites=bad, expected=exp, score=int(route_ok) + int(cite_ok) + int(conf_ok))

def ask(n, mode):
    c = Q[int(n)]; m = pm(); fn = RUNS / f"ask{n}_{mode}.json"
    if mode == "rag":
        fnol = next(t for i, t in corpus().items() if i == f"FNOL-{c.split('-')[1]}")
        # metadata filter for this claim's own documents + similarity search over the policy wording and guidelines
        own = [(i, t, 1.0) for i, t in corpus().items() if i.split("#")[0].endswith(c.split("-")[1])]
        hits = own + retrieve(f"triage route coverage {fnol}", k=4, kinds=("WORD", "GL"))
        user = f"Claim {c}. Triage date {TODAY}.\nRETRIEVED CONTEXT:\n" + "\n".join(f"[{i}] {t}" for i, t, _ in hits) + "\n\nWhich route?"
        con.print(f"[{DIM}]plain RAG: claim documents + top 4 policy chunks by TF-IDF:[/] " + ", ".join(i for i, _, _ in hits))
        sysm = SYS_RAG; e = None
    else:
        user, e = pack(c); sysm = SYS_SEM
        con.print(f"[{DIM}]Semantica evidence pack: {len(claim_facts(c))} facts with sources, {len(e['conflicts'])} conflict(s), "
                  f"clauses in force, {e['guideline']}, rule check -> {e['route']}[/]")
    con.print(f"[{DIM}]asking the local model ...[/]")
    raw, secs, usage = llm(sysm, user); j = parse(raw)
    final = j["route"]; guard = ""
    if mode == "semantica" and j["route"] != e["route"]:
        guard = f"model said {j['route']}, rules say {e['route']}: held for a human"; final = "REFER_ADJUSTER"
    j["final_route"] = final; gr = grade(c, dict(j, route=final), m)
    rec = dict(n=int(n), claim=c, mode=mode, model=MODEL, seed=42, temperature=0, prompt_sha256=sha(sysm + "\n" + user), system=sysm,
               user=user, raw=raw, answer=j, guard=guard, grade=gr, seconds=secs, usage=usage)
    if mode == "semantica":   # write the decision back as an auditable, hash-chained record
        g, pe = build_graph(); cited = [x for x in j["cited"] if m.storage.retrieve(x)]
        did = g.record_decision(category="claim_triage", scenario=f"Triage {c}", reasoning=j.get("rationale", ""), outcome=final,
                                confidence=0.9 if not guard else 0.5, entities=[c] + cited, decision_maker="triage-agent",
                                metadata=dict(guideline=e["guideline"], prompt_sha256=rec["prompt_sha256"], model=MODEL))
        pe.record_policy_application(did, "GL-TRIAGE", e["guideline"].split("v")[-1])
        did = f"DEC-{c.split('-')[1]}-{rec['prompt_sha256'][:6]}"
        m.track_entity(did, source="triage-agent", entity_type="Decision", used_entities=cited, agent_id="triage-agent",
                       acted_on_behalf_of="claims-operations", activity_id="claim_triage",
                       metadata=dict(claim=c, route=final, model_route=j["route"], rule_route=e["route"], guideline=e["guideline"],
                                     model=MODEL, seed=42, temperature=0, prompt_sha256=rec["prompt_sha256"]))
        rec["decision_id"] = did; open(RUNS / "last_decision.txt", "w").write(did)
    json.dump(rec, open(fn, "w"), indent=1)
    col = MINT if gr["route_ok"] else RED
    con.print(Panel(f"Route: [bold {col}]{final}[/]   [{DIM}](expected {gr['expected']})[/]\n"
                    f"Rationale: {j.get('rationale', '')}\n"
                    f"Cited: {', '.join(j['cited']) or '(nothing)'}\n"
                    f"Conflicts flagged: {', '.join(str(x.get('property')) for x in j['conflicts']) or 'none'}"
                    + (f"\n[{AMBER}]Guardrail: {guard}[/]" if guard else "")
                    + "".join(f"\n[{RED}]Bad citation: {x} ({why})[/]" for x, why in gr["bad_cites"])
                    + (f"\n[{MINT}]Audit record: {rec['decision_id']} (hash-chained)[/]" if mode == "semantica" else f"\n[{DIM}]Audit record: none[/]"),
                    title=f"{c}  |  {'plain RAG' if mode == 'rag' else 'Semantica-backed'}  |  score {gr['score']}/3",
                    border_style=col, width=112))

# ---------------------------------------------------------------- audit, tamper, export
def audit(did=None):
    m = pm(); did = did or (RUNS / "last_decision.txt").read_text().strip()
    if did.startswith("CLM-"): did = next(json.load(open(f))["decision_id"] for f in RUNS.glob("ask*_semantica.json") if json.load(open(f))["claim"] == did)
    e = m.storage.retrieve(did)
    md = e.metadata; rec = next(json.load(open(f)) for f in RUNS.glob("ask*_semantica.json") if json.load(open(f)).get("decision_id") == did)
    t = Table(title=f"Replay {did}", box=box.SIMPLE_HEAVY, title_style=f"bold {MINT}", show_header=False)
    t.add_column(style=DIM); t.add_column()
    t.add_row("claim / route", f"{md['claim']} -> {md['route']}  (model {md['model_route']}, rules {md['rule_route']})")
    t.add_row("who", f"{e.agent_id} on behalf of {e.acted_on_behalf_of}, {e.timestamp[:19]} UTC")
    t.add_row("model", f"{md['model']}, temperature {md['temperature']}, seed {md['seed']}, guideline {md['guideline']}")
    same = sha(rec["system"] + "\n" + rec["user"]) == md["prompt_sha256"]
    t.add_row("prompt sha256", f"{md['prompt_sha256'][:16]}...  re-hashed from the saved prompt: {'MATCH' if same else 'DIFFERENT'}")
    con.print(t)
    t2 = Table(title="Lineage: decision -> facts -> source documents", box=box.SIMPLE_HEAVY, title_style=f"bold {MINT}")
    for col in ["Used", "Says", "From", "Document fingerprint", "Grounded"]: t2.add_column(col)
    for u in e.used_entities:
        x = m.storage.retrieve(u); d = x if x.entity_type == "SourceDocument" else m.storage.retrieve(x.source_document)
        doc_id = u if x.entity_type == "SourceDocument" else x.source_document
        live = sha((H / "docs_corpus" / f"{doc_id}.md").read_bytes()) if d else ""
        fp = f"{d.metadata['sha256'][:12]} {'unchanged' if d and d.metadata['sha256'] == live else 'CHANGED'}" if d else ""
        t2.add_row(u, (x.metadata.get("property", "") + " = " + x.metadata.get("value", "")) if x.metadata.get("property") else (x.source_quote or x.metadata.get("kind", ""))[:40],
                   f"{doc_id} {x.source_location or ''}", fp, "yes" if x.entity_type != "Fact" or grounded(x) else f"[{RED}]no[/]")
    con.print(t2)
    ch = m.verify_chain(); ck = sum(verify_checksum(x) for x in m.trace_lineage(did))
    con.print(f"Hash chain: [bold {MINT if ch['valid'] else RED}]{'valid' if ch['valid'] else 'BROKEN'}[/] over {ch['total_entries']} entries;  "
              f"decision checksum {'ok' if verify_checksum(e) else 'BAD'}")

def grounded(e):
    """Re-read the source document: the quote must still be in it, and the value must still be in the quote."""
    doc = H / "docs_corpus" / f"{e.source_document}.md"
    if not doc.exists() or not e.source_quote: return False
    v = str(e.metadata.get("value", "")); q = e.source_quote
    if q not in doc.read_text(): return False
    return v in q.replace(",", "") if re.fullmatch(r"[\d-]+", v) else True   # numbers and dates must match the quote exactly

def tamper():
    def edit(sql, args, label):
        cp = RUNS / "tampered.db"; shutil.copy(DB, cp); db = sqlite3.connect(cp); db.execute(sql, args); db.commit(); db.close()
        e = ProvenanceManager(storage_path=str(cp)).storage.retrieve("F12"); ck, gd = verify_checksum(e), grounded(e); cp.unlink()
        col = lambda ok: MINT if ok else RED
        con.print(f"{label}\n   checksum (who, where, when, lineage): [bold {col(ck)}]{'ok' if ck else 'TAMPERED'}[/]    "
                  f"grounding (quote still in the source): [bold {col(gd)}]{'ok' if gd else 'NOT FOUND'}[/]")
    e = pm().storage.retrieve("F12")
    con.print(f"F12 today: amount = {e.metadata['value']}, from {e.source_document}, \"{e.source_quote}\"   "
              f"checksum [{MINT}]ok[/]  grounding [{MINT}]{'ok' if grounded(e) else 'NOT FOUND'}[/]\n")
    md = dict(e.metadata, value="3600")
    edit("UPDATE provenance SET metadata=?, source_quote=? WHERE entity_id='F12'", (json.dumps(md), "Damage estimate $3,600"),
         "1) someone edits the value on a copy: 6300 -> 3600")
    edit("UPDATE provenance SET source_document=? WHERE entity_id='F12'", ("FNOL-2603",),
         "2) someone re-attributes F12 to a different document: ADJ-2603 -> FNOL-2603")
    con.print(f"\n[{DIM}]Semantica 0.7.0's checksum covers attribution and lineage, not the value. Pair it with a grounding check.[/]")

def run_of(n, mode):
    f = RUNS / f"ask{n}_{mode}.json"
    if not f.exists(): return None
    r = json.load(open(f)); r["grade"] = grade(r["claim"], dict(r["answer"], route=r["answer"]["final_route"]), pm()); return r

def compare():
    t = Table(title="Plain RAG vs Semantica-backed agent (same local model)", box=box.SIMPLE_HEAVY, title_style=f"bold {MINT}")
    for col in ["Claim", "Expected", "Plain RAG", "Semantica", "Bad cites (RAG)", "Conflicts handled (RAG / Sem)"]: t.add_column(col)
    for n, c in Q.items():
        a, b = run_of(n, "rag"), run_of(n, "semantica")
        if not a or not b: continue
        fmt = lambda r: f"[{MINT if r['grade']['route_ok'] else RED}]{r['answer']['final_route']}[/]"
        cf = lambda r: "yes" if r["grade"]["conf_ok"] else "[" + RED + "]no[/]"
        t.add_row(c, EXPECT[c][0], fmt(a), fmt(b), ", ".join(x for x, _ in a["grade"]["bad_cites"]) or "-", f"{cf(a)} / {cf(b)}")
    con.print(t)

def scorecard():
    t = Table(title="Scorecard (3 points per claim: right route, valid citations, conflicts handled)", box=box.SIMPLE_HEAVY, title_style=f"bold {MINT}")
    for col in ["Check", "Plain RAG", "Semantica"]: t.add_column(col)
    S = {md: [run_of(n, md) for n in Q] for md in ("rag", "semantica")}
    if any(r is None for v in S.values() for r in v): con.print("run all ten asks first"); return
    for k, lab in [("route_ok", "Right route"), ("cite_ok", "Citations valid and in force"), ("conf_ok", "Conflicts flagged correctly")]:
        t.add_row(lab, *[f"{sum(r['grade'][k] for r in S[md])} / 5" for md in ("rag", "semantica")])
    t.add_row("[bold]Total[/]", *[f"[bold]{sum(r['grade']['score'] for r in S[md])} / 15[/]" for md in ("rag", "semantica")])
    t.add_row("Replayable audit record", "[" + RED + "]0 / 5[/]", f"[{MINT}]{sum(1 for r in S['semantica'] if r.get('decision_id'))} / 5[/]")
    t.add_row("Avg prompt tokens", *[str(round(sum(r['usage'].get('prompt_tokens', 0) for r in S[md]) / 5)) for md in ("rag", "semantica")])
    con.print(t)
    json.dump({md: [dict(claim=r["claim"], route=r["answer"]["final_route"], **{k: r["grade"][k] for k in ("route_ok", "cite_ok", "conf_ok", "score")})
                    for r in S[md]] for md in S}, open(RUNS / "scorecard.json", "w"), indent=1)

def export():
    m = pm(); out = H / "export"; out.mkdir(exist_ok=True)
    ttl = m.export_prov(format="turtle"); (out / "provenance.ttl").write_text(ttl)
    ents = m.storage.retrieve_all() if hasattr(m.storage, "retrieve_all") else None
    if ents is None:
        db = sqlite3.connect(DB); ids = [r[0] for r in db.execute("SELECT entity_id FROM provenance_entries")]; ents = [m.storage.retrieve(i) for i in ids]
    keep = ["entity_id", "entity_type", "source_document", "source_location", "source_quote", "agent_id", "confidence", "timestamp", "checksum", "previous_checksum"]
    with open(out / "provenance_entries.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(keep + ["used_entities"])
        for e in ents:
            if ":v:" in e.entity_id: continue
            w.writerow([getattr(e, k) for k in keep] + [";".join(e.used_entities)])
    with open(out / "lineage_edges.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["from_id", "to_id", "relation"])
        for e in ents:
            if ":v:" in e.entity_id: continue
            if e.entity_type in ("Fact", "PolicyClause"): w.writerow([e.entity_id, e.source_document, "wasDerivedFrom"])
            for u in e.used_entities: w.writerow([e.entity_id, u, "used"])
    n = sum(1 for _ in open(out / "provenance_entries.csv")) - 1; ne = sum(1 for _ in open(out / "lineage_edges.csv")) - 1
    con.print(f"export/provenance.ttl  [{DIM}]W3C PROV-O Turtle, {len(ttl.splitlines())} lines[/]")
    con.print(f"export/provenance_entries.csv  [{DIM}]{n} rows[/]    export/lineage_edges.csv  [{DIM}]{ne} rows[/]")
    con.print(f"[{DIM}]Flat tables: load them into a Fabric lakehouse (OneLake) as Delta tables to query the audit trail with SQL.[/]")

if __name__ == "__main__":
    a = sys.argv[1:]; cmd = a[0] if a else "help"
    if cmd == "build": build()
    elif cmd == "facts": facts(a[1])
    elif cmd == "conflicts": conflicts(a[1] if len(a) > 1 else None)
    elif cmd == "rules": show_rules(a[1])
    elif cmd == "ask": ask(a[1], a[a.index("--mode") + 1] if "--mode" in a else "semantica")
    elif cmd == "pack": print(pack(Q[int(a[1])])[0])
    elif cmd == "audit": audit(a[1] if len(a) > 1 else None)
    elif cmd == "tamper": tamper()
    elif cmd == "compare": compare()
    elif cmd == "scorecard": scorecard()
    elif cmd == "export": export()
    else: print(__doc__)
