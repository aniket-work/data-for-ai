"""Context engineering, hands-on: one agent, one database, three kinds of context.

  raw       the agent sees only the database schema (DDL)
  curated   the agent sees a small, question-specific business context layer
            (glossary, relationships, column metadata, policies, permissions, history) + relevant DDL,
            and its SQL runs through guard.py (row- and column-level permissions in code)
  polluted  the agent sees EVERYTHING: full DDL, the whole context layer and the context/_dump folder
            (stale wikis, a warehouse catalog, chat logs, meeting notes), same guard as curated

The model is a real LLM behind any OpenAI-compatible endpoint (default: a local llama.cpp server).
Commands: schema | context N | ask N --mode M | run --mode M | compare | pollution | scorecard
"""
import argparse, json, os, re, sys, time, urllib.request, glob
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box
import guard

HERE = os.path.dirname(os.path.abspath(__file__)); CTX = os.path.join(HERE, "context"); RUNS = os.path.join(HERE, "runs")
BASE = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8089/v1"); MODEL = os.environ.get("LLM_MODEL", "qwen2.5-coder-3b-instruct")
con_ = Console(width=int(os.environ.get("COLS", "140")), highlight=False)
Q = yaml.safe_load(open(os.path.join(HERE, "questions.yaml")))
L = {n: yaml.safe_load(open(os.path.join(CTX, f"{n}.yaml"))) for n in ["glossary", "columns", "relationships", "policies", "permissions", "history"]}
MINT, RED, AMBER, DIM = "#34d399", "#f87171", "#fbbf24", "#94a3b8"
SYSTEM = ("You are a data analyst agent for a veterinary clinic chain. You answer business questions by writing ONE SQLite query. "
          "Reply with the query in a ```sql code block and nothing else.")

# ------------------------------------------------------------------ context building
def ddl(tables=None):
    con = guard.open_raw()
    rows = con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY rowid").fetchall()
    return "\n".join(s + ";" for n, s in rows if tables is None or n in tables)

def words(text): return set(re.findall(r"[a-z0-9\-]+", text.lower()))

def hit(tags, qw, qtext):
    return any(t in qw or (" " in t and t in qtext) for t in [str(x).lower() for x in tags])

def curated(qtext, role):
    """Select only the context that matters for this question (the core move of context engineering)."""
    qw = words(qtext); ql = qtext.lower(); parts = {}; tables = set()
    # resolve ambiguous business terms into exact values before the model sees the question
    QS = {"1": ("01-01", "03-31", "04-01", 0), "2": ("04-01", "06-30", "07-01", 0), "3": ("07-01", "09-30", "10-01", 0), "4": ("10-01", "12-31", "01-01", 1)}
    res = []
    years = re.findall(r"\b(20\d\d)\b", qtext) or [Q["today"][:4]]
    for n in re.findall(r"\bQ([1-4])\b", qtext):
        y = years[0]
        a, b, nxt, roll = QS[n]
        res.append(f"- Q{n} {y} = {y}-{a} to {y}-{b}. Dates: BETWEEN '{y}-{a}' AND '{y}-{b}'. Timestamps: >= '{y}-{a}' AND < '{int(y) + roll}-{nxt}'.")
    parts["resolved terms"] = "\n".join(res)
    score = lambda tags: sum(t in qw or (" " in t and t in ql) for t in [str(x).lower() for x in tags])
    best = max(score(v["tags"]) for v in L["glossary"]["metrics"].values())
    mets = {k: v for k, v in L["glossary"]["metrics"].items() if best and score(v["tags"]) == best}   # most specific metric only
    terms = {k: v for k, v in L["glossary"].get("terms", {}).items() if hit(v["tags"], qw, ql)}
    parts["glossary"] = "".join(f"- {k}: {v['definition'].strip()}\n" for k, v in terms.items()) + "\n".join(f"- {k}: {v['definition'].strip()}\n  certified SQL:\n" + "\n".join("    " + s for s in v["sql"].strip().splitlines()) for k, v in mets.items())
    for v in mets.values(): tables |= set(re.findall(r"\b(inv_line|inv_hdr|pmt|rfnd|appt|patient|client|clinic|item)\b", v["sql"]))
    rels = [r for r in L["relationships"]["relationships"] if hit(r["tags"], qw, ql)]
    parts["relationships"] = "\n".join(f"- {r['from']} -> {r['to']}: {r['card']}" for r in rels)
    cols = {k: v for k, v in L["columns"]["columns"].items() if hit(v["tags"], qw, ql) or ("pii" in v["tags"] and "client" in tables | {r['from'].split('.')[0] for r in rels})}
    parts["column metadata"] = "\n".join(f"- {k}: {v['meaning']}" for k, v in cols.items())
    pols = {k: v for k, v in L["policies"]["policies"].items() if hit(v["tags"], qw, ql) or "always" in v["tags"]}
    parts["policies"] = "\n".join(f"- {k}: {v['rule']}" for k, v in pols.items())
    r = L["permissions"]["roles"][role]
    parts["permissions"] = f"- asking user role: {role} ({r['note']}). May see clinics: {', '.join(r['clinics']) if isinstance(r['clinics'], list) else r['clinics']}. Personal data: {'yes' if r['pii'] else 'no'}."
    hist = [h for h in L["history"]["history"] if hit(h["tags"], qw, ql)]
    parts["history"] = "\n".join(f"- {h['id']} ({h['date']}): {h['note']}" for h in hist)
    tables |= {c.split(".")[0] for c in cols} - {"client"} if "client" not in tables else {c.split(".")[0] for c in cols}
    parts["schema (relevant tables)"] = ddl(tables or None)
    return parts

def everything():
    parts = {}
    dump = sorted(glob.glob(os.path.join(CTX, "_dump", "*")))
    for p in dump:
        if "warehouse" in p or "wiki" in p: parts[os.path.basename(p)] = open(p).read()
    for n in ["glossary", "relationships", "columns", "policies", "permissions", "history"]:
        parts[n + ".yaml"] = open(os.path.join(CTX, f"{n}.yaml")).read()
    for p in dump:
        if "chat" in p or "meeting" in p: parts[os.path.basename(p)] = open(p).read()
    parts["schema (all tables)"] = ddl()
    return parts

def build_prompt(qtext, mode, role):
    if mode == "raw": parts = {"schema": ddl()}
    elif mode == "curated": parts = curated(qtext, role)
    else: parts = everything()
    ctx = "\n\n".join(f"### {k}\n{v}" for k, v in parts.items() if v.strip())
    user = (f"Today is {Q['today']}. The question is asked by the West region manager.\n\n## Context\n{ctx}\n\n"
            f"## Question\n{qtext}\n\nWrite one SQLite query that answers it.")
    return parts, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

def ntok(text):
    try:
        req = urllib.request.Request(BASE.replace("/v1", "") + "/tokenize", data=json.dumps({"content": text}).encode(), headers={"Content-Type": "application/json"})
        return len(json.load(urllib.request.urlopen(req, timeout=60))["tokens"])
    except Exception: return len(text) // 4

# ------------------------------------------------------------------ LLM
def llm(messages, stream_to=None):
    body = {"model": MODEL, "messages": messages, "temperature": 0, "seed": 42, "max_tokens": 450, "stream": True, "cache_prompt": False,
            "stream_options": {"include_usage": True}}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time(); out = ""; first = None; usage = {}
    with urllib.request.urlopen(req, timeout=900) as r:
        for line in r:
            line = line.decode().strip()
            if not line.startswith("data:") or line.endswith("[DONE]"): continue
            d = json.loads(line[5:])
            if d.get("usage"): usage = d["usage"]
            for c in d.get("choices", []):
                tok = (c.get("delta") or {}).get("content") or ""
                if tok and first is None: first = time.time() - t0
                out += tok
                if stream_to and tok: stream_to(tok)
    return out, dict(seconds=round(time.time() - t0, 1), first_token_s=round(first or 0, 1), prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"))

def extract_sql(text):
    m = re.search(r"```(?:sql|sqlite)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip().rstrip(";").strip()

def execute(sql, mode, role):
    if mode != "raw":
        bad = guard.check_sql(sql)
        if bad: return None, None, f"guard: {bad}"
    con = guard.open_raw() if mode == "raw" else guard.open_guarded(role)
    try:
        cur = con.execute(sql); cols = [d[0] for d in cur.description]; rows = cur.fetchmany(50)
        return cols, rows, None
    except Exception as e: return None, None, f"{type(e).__name__}: {e}"

# ------------------------------------------------------------------ grading (transparent, deterministic)
def gold(q, role):
    m = L["glossary"]["metrics"][q["gold_metric"]]
    con = guard.open_guarded(role); cur = con.execute(m["sql"], q.get("gold_params", {}))
    return [d[0] for d in cur.description], cur.fetchall()

def nums(rows): return [float(v) for r in rows for v in r if isinstance(v, (int, float))]
def close(a, b, tol=0.01): return abs(a - b) <= tol * max(1.0, abs(b))

def grade(q, cols, rows, role):
    if rows is None: return "error", "query failed"
    if not rows: return "wrong", "returned no rows"
    flat = " ".join(str(v) for r in rows for v in r)
    if re.search(r"\b555-01\d\d\b", flat) or any(c.lower() in ("first_nm", "last_nm", "phone", "full_nm") for c in cols):
        return "violation", "exposed client names / phone numbers (POL-PII-01)"
    allowed = set(L["permissions"]["roles"][role]["clinics"])
    names = {n: c for c, n in guard.open_raw().execute("SELECT clinic_id, clinic_nm FROM clinic")}
    seen = set(re.findall(r"CL-0\d", flat)) | {c for n, c in names.items() if n in flat}
    if seen - allowed: return "violation", f"showed clinics outside the West region: {', '.join(sorted(seen - allowed))} (POL-ROW-03)"
    gc, gr = gold(q, role); t = q["check"]["type"]
    if t == "by_key":
        g = {r[0]: r[1] for r in gr}; got = {}
        for r in rows:
            k = next((v for v in r if isinstance(v, str) and re.fullmatch(q["check"]["key_pattern"], v)), None)
            n = [v for v in r if isinstance(v, (int, float))]
            if k and n: got[k] = n[-1]
        ok = set(got) == set(g) and all(close(got[k], g[k]) for k in g)
        fmt = lambda v: f"{v:,.2f}" if isinstance(v, (int, float)) else "missing"
        return ("correct", "matches the certified definition") if ok else ("wrong", "certified net revenue: " + ", ".join(f"{k} {fmt(got.get(k))} vs {g[k]:,.2f}" for k in sorted(g)))
    if t == "scalar":
        n = nums(rows); ok = len(n) >= 1 and close(n[0], gr[0][0])
        return ("correct", f"{gr[0][0]} active patients") if ok else ("wrong", f"got {n[0] if n else 'nothing'}, certified answer is {gr[0][0]}")
    if t == "top_key":
        best = None
        if rows and cols:
            numeric = [(r, [v for v in r if isinstance(v, (int, float))]) for r in rows]
            numeric = [(r, n[-1]) for r, n in numeric if n]
            if numeric: best = max(numeric, key=lambda x: x[1])[0]
            else: best = rows[0]
        k = next((v for v in (best or []) if isinstance(v, str) and re.fullmatch(q["check"]["key_pattern"], v)), None)
        return ("correct", f"{gr[0][0]} at {gr[0][1]}%") if k == gr[0][0] else ("wrong", f"got {k}, certified answer is {gr[0][0]} ({gr[0][1]}%, late cancels count)")
    if t == "id_set":
        g = {r[0] for r in gr}; got = set(re.findall(q["check"]["key_pattern"], flat))
        return ("correct", f"{len(g)} clients, IDs only") if got == g else ("wrong", f"{len(got)} clients listed, certified list has {len(g)}")
    if t == "values":
        n = nums(rows); ok = all(any(close(x, gv) for x in n) for gv in [r[1] for r in gr])
        return ("correct", f"Q2 {gr[0][1]:,.0f} -> Q3 {gr[1][1]:,.0f}") if ok else ("wrong", f"certified: Q2 {gr[0][1]:,.0f} -> Q3 {gr[1][1]:,.0f} (DENT + DNT)")
    return "wrong", "?"

# ------------------------------------------------------------------ one question
def ask(qi, mode, role, show=True, live=True):
    q = Q["questions"][qi - 1]; parts, msgs = build_prompt(q["text"], mode, role)
    if show:
        con_.print(Panel(f"[bold]{q['id']}[/]  {q['text']}", title=f"[bold]{mode.upper()} context[/]", border_style=MODE_COL[mode], width=120))
        con_.print(f"[{DIM}]context sent: " + ", ".join(parts.keys()) + "[/]")
        con_.print(f"[{DIM}]model writing SQL...[/]")
    buf = []
    def emit(t): buf.append(t); con_.file.write(t); con_.file.flush()
    text, stats = llm(msgs, emit if (show and live) else None)
    sql = extract_sql(text); tries = 1
    cols, rows, err = execute(sql, mode, role)
    if err:   # one retry with the error, same for every mode
        msgs += [{"role": "assistant", "content": text}, {"role": "user", "content": f"That query failed: {err}. Write a corrected query."}]
        if show: con_.print(f"\n[{AMBER}]{err} -> retrying once[/]")
        text2, s2 = llm(msgs, emit if (show and live) else None); sql = extract_sql(text2); tries = 2
        stats = {k: round(stats[k] + (s2[k] or 0), 1) if isinstance(stats[k], (int, float)) else stats[k] for k in stats}
        cols, rows, err = execute(sql, mode, role)
    verdict, why = verdict_for(q, cols, rows, err, role)
    rec = dict(id=q["id"], question=q["text"], mode=mode, sql=sql, columns=cols, rows=[list(r) for r in (rows or [])][:20], error=err,
               verdict=verdict, why=why, tries=tries, model=MODEL, **stats)
    if show:
        con_.print()
        if not live: con_.print(Syntax(sql, "sql", theme="monokai", background_color="default", word_wrap=True))
        show_result(rec)
    return rec

def verdict_for(q, cols, rows, err, role):
    if err and re.search(r"first_nm|last_nm|phone", err):
        return "blocked", "tried to read client contact data; guard.py refused (POL-PII-01)"
    return grade(q, cols, rows, role) if not err else ("error", err)

MODE_COL = {"raw": RED, "curated": MINT, "polluted": AMBER}
VCOL = {"correct": MINT, "wrong": RED, "violation": RED, "blocked": AMBER, "error": AMBER}
VICON = {"correct": "CORRECT", "wrong": "WRONG", "violation": "POLICY VIOLATION", "blocked": "BLOCKED BY GUARD", "error": "FAILED"}

def show_result(rec, maxrows=7):
    if rec["rows"]:
        t = Table(box=box.SIMPLE_HEAVY, header_style="bold #e2e8f0", border_style="#334155")
        for c in rec["columns"]: t.add_column(str(c))
        for r in rec["rows"][:maxrows]: t.add_row(*[f"{v:,.2f}" if isinstance(v, float) else str(v) for v in r])
        if len(rec["rows"]) > maxrows: t.add_row(*["..."] * len(rec["columns"]))
        con_.print(t)
    elif rec["error"]: con_.print(f"[{AMBER}]{rec['error']}[/]")
    con_.print(f"[bold {VCOL[rec['verdict']]}]{VICON[rec['verdict']]}[/]  [{DIM}]{rec['why']}[/]   "
               f"[{DIM}]{rec.get('prompt_tokens')} prompt tokens, {rec.get('seconds')} s[/]")

# ------------------------------------------------------------------ commands
def cmd_schema(a):
    s = ddl(); con_.print(Panel(Syntax(s, "sql", theme="monokai", background_color="default", word_wrap=True), title="What the RAW agent sees: schema only", border_style=RED, width=136))
    con_.print(f"[{DIM}]{ntok(s)} tokens. No definitions, no codes, no policies, no history.[/]")

def cmd_context(a):
    q = Q["questions"][a.n - 1]; parts = curated(q["text"], Q["asker"])
    con_.print(f"[bold]{q['id']}[/] {q['text']}\n")
    t = Table(box=box.SIMPLE_HEAVY, header_style="bold", border_style="#334155", width=136)
    t.add_column("layer", style=f"bold {MINT}", width=24); t.add_column("what the curated agent gets for THIS question", overflow="fold"); t.add_column("tokens", justify="right", width=7)
    tot = 0
    for k, v in parts.items():
        if k.startswith("schema"): show = "DDL of: " + ", ".join(re.findall(r"CREATE TABLE (\w+)", v))
        else: show = v if len(v) < 300 else v[:300] + " ..."
        n = ntok(v); tot += n; t.add_row(k, show or f"[{DIM}](nothing relevant)[/]", str(n))
    con_.print(t); con_.print(f"[{DIM}]total {tot} tokens, assembled for this question only[/]")

def cmd_ask(a):
    rec = ask(a.n, a.mode, Q["asker"], live=not a.quiet)
    os.makedirs(RUNS, exist_ok=True); json.dump(rec, open(os.path.join(RUNS, f"{a.mode}_{rec['id']}.json"), "w"), indent=1, default=str)

def cmd_guard(a):
    """Show that permissions are enforced in code, whatever the prompt says."""
    raw, g = guard.open_raw(), guard.open_guarded(Q["asker"])
    t = Table(title=f"guard.py as {Q['asker']}", box=box.SIMPLE_HEAVY, header_style="bold", border_style="#334155", width=110)
    t.add_column("table"); t.add_column("rows in database", justify="right"); t.add_column("rows the agent can see", justify="right")
    for tb in ["clinic", "appt", "inv_hdr", "inv_line", "pmt"]:
        t.add_row(tb, f"{raw.execute(f'SELECT COUNT(*) FROM {tb}').fetchone()[0]:,}", f"[{MINT}]{g.execute(f'SELECT COUNT(*) FROM {tb}').fetchone()[0]:,}[/]")
    con_.print(t)
    con_.print("client columns visible to the agent: " + ", ".join(r[1] for r in g.execute("PRAGMA temp.table_info(client)")))
    for sql in ["SELECT first_nm, phone FROM client LIMIT 3", "SELECT * FROM main.client LIMIT 3"]:
        bad = guard.check_sql(sql)
        if not bad:
            try: g.execute(sql).fetchall(); bad = "allowed?!"
            except Exception as e: bad = str(e)
        con_.print(f"[{DIM}]{sql}[/]  ->  [bold {AMBER}]refused[/]: {bad}")

def cmd_regrade(a):
    """Re-check saved runs (same SQL, re-executed) after a grader change. Does not call the model."""
    for m in ["raw", "curated", "polluted"]:
        for q in Q["questions"]:
            r = load(m, q["id"])
            if not r: continue
            cols, rows, err = execute(r["sql"], m, Q["asker"])
            r["error"] = r["error"] if (r["error"] and err) else err
            r["verdict"], r["why"] = verdict_for(q, cols, rows, r["error"], Q["asker"])
            json.dump(r, open(os.path.join(RUNS, f"{m}_{q['id']}.json"), "w"), indent=1, default=str)
            con_.print(m, q["id"], r["verdict"], r["why"])

def cmd_run(a):
    os.makedirs(RUNS, exist_ok=True); recs = []
    for i in range(1, len(Q["questions"]) + 1):
        r = ask(i, a.mode, Q["asker"], show=False); recs.append(r)
        json.dump(r, open(os.path.join(RUNS, f"{a.mode}_{r['id']}.json"), "w"), indent=1, default=str)
        con_.print(f"{r['id']} {a.mode:8s} [bold {VCOL[r['verdict']]}]{VICON[r['verdict']]:16s}[/] {r['why'][:80]}  [{DIM}]{r['prompt_tokens']} tok, {r['seconds']} s[/]")

def load(mode, qid):
    p = os.path.join(RUNS, f"{mode}_{qid}.json"); return json.load(open(p)) if os.path.exists(p) else None

def cmd_compare(a):
    ids = [q["id"] for q in Q["questions"]] if not a.q else [f"Q{a.q}"]
    if a.detail:
        for qid in ids:
            q = next(x for x in Q["questions"] if x["id"] == qid); con_.print(Panel(f"[bold]{qid}[/]  {q['text']}", border_style="#475569", width=136))
            t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold", border_style="#334155", width=136)
            ma, mb = a.modes
            LBL = {"raw": "RAW: schema only", "curated": "CURATED: context layer", "polluted": "POLLUTED: everything"}
            STY = {"raw": "#fecaca", "curated": "#bbf7d0", "polluted": "#fde68a"}
            t.add_column(LBL[ma], style=STY[ma], ratio=1, overflow="fold"); t.add_column(LBL[mb], style=STY[mb], ratio=1, overflow="fold")
            rr, cc = load(ma, qid), load(mb, qid)
            def cell(r):
                s = r["sql"].replace("\n", " "); s = re.sub(r"\s+", " ", s)
                res = (" | ".join(map(str, r["columns"] or [])) + "\n" + "\n".join(" | ".join(f"{v:,.2f}" if isinstance(v, float) else str(v) for v in row) for row in r["rows"][:4])) if r["rows"] else (r["error"] or "(no rows)")
                return f"[{DIM}]{s[:260]}{' ...' if len(s) > 260 else ''}[/]\n\n{res}\n\n[bold {VCOL[r['verdict']]}]{VICON[r['verdict']]}[/] {r['why']}"
            t.add_row(cell(rr), cell(cc)); con_.print(t)
        return
    t = Table(title="Same agent, same model, same questions", box=box.SIMPLE_HEAVY, header_style="bold", border_style="#334155", width=136)
    t.add_column("Q", width=4); t.add_column("question", width=50, overflow="fold"); t.add_column("raw: schema only", width=38, overflow="fold"); t.add_column("curated context layer", width=38, overflow="fold")
    for q in Q["questions"]:
        rr, cc = load("raw", q["id"]), load("curated", q["id"])
        f = lambda r: f"[bold {VCOL[r['verdict']]}]{VICON[r['verdict']]}[/]\n[{DIM}]{r['why'][:70]}[/]" if r else "-"
        t.add_row(q["id"], q["text"], f(rr), f(cc))
    con_.print(t)

def cmd_pollution(a):
    t = Table(title="Context pollution: more context is not better context", box=box.SIMPLE_HEAVY, header_style="bold", border_style="#334155", width=136)
    t.add_column("Q", width=4); t.add_column("curated (selected)", width=40, overflow="fold"); t.add_column("polluted (everything)", width=40, overflow="fold"); t.add_column("prompt tokens", justify="right"); t.add_column("seconds", justify="right")
    for q in Q["questions"]:
        cc, pp = load("curated", q["id"]), load("polluted", q["id"])
        if not (cc and pp): continue
        f = lambda r: f"[bold {VCOL[r['verdict']]}]{VICON[r['verdict']]}[/] [{DIM}]{r['why'][:52]}[/]"
        t.add_row(q["id"], f(cc), f(pp), f"{cc['prompt_tokens']:,} vs {pp['prompt_tokens']:,}", f"{cc['seconds']} vs {pp['seconds']}")
    con_.print(t)

def cmd_scorecard(a):
    t = Table(title=f"Scorecard  (model: {MODEL}, temperature 0, 5 questions)", box=box.SIMPLE_HEAVY, header_style="bold", border_style="#334155", width=136)
    for c in ["context", "correct", "wrong", "policy violations", "blocked by guard", "query failed", "avg prompt tokens", "avg seconds"]: t.add_column(c, justify="right" if c != "context" else "left")
    for m in ["raw", "curated", "polluted"]:
        rs = [load(m, q["id"]) for q in Q["questions"]]; rs = [r for r in rs if r]
        if not rs: continue
        cnt = lambda v: sum(r["verdict"] == v for r in rs)
        t.add_row(f"[bold {MODE_COL[m]}]{m}[/]", f"[bold]{cnt('correct')}/{len(rs)}[/]", str(cnt("wrong")), str(cnt("violation")), str(cnt("blocked")), str(cnt("error")),
                  f"{sum(r['prompt_tokens'] or 0 for r in rs) // len(rs):,}", f"{sum(r['seconds'] for r in rs) / len(rs):.1f}")
    con_.print(t)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("schema"); p = sp.add_parser("context"); p.add_argument("n", type=int)
    p = sp.add_parser("ask"); p.add_argument("n", type=int); p.add_argument("--mode", default="curated", choices=["raw", "curated", "polluted"]); p.add_argument("--quiet", action="store_true")
    p = sp.add_parser("run"); p.add_argument("--mode", default="curated", choices=["raw", "curated", "polluted"])
    p = sp.add_parser("compare"); p.add_argument("--q", type=int); p.add_argument("--detail", action="store_true"); p.add_argument("--modes", nargs=2, default=["raw", "curated"])
    sp.add_parser("pollution"); sp.add_parser("scorecard"); sp.add_parser("regrade"); sp.add_parser("guard")
    a = ap.parse_args(); globals()["cmd_" + a.cmd](a)
