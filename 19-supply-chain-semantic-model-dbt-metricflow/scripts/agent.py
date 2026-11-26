"""A small local agent that answers supply chain questions from the Ossie model.

It never writes SQL. It can only (1) ask MetricFlow for governed metrics and (2) search the contract,
incident and policy documents. The model's own ai_context (instructions, synonyms) goes into the prompt.
LLM: any OpenAI-compatible server; here llama.cpp's llama-server with Qwen3-4B-Instruct on CPU.

  python scripts/agent.py "Did Pangrove breach its SLA last quarter, and why?"
"""
import csv, json, math, os, re, subprocess, sys, tempfile, time
from collections import Counter
from pathlib import Path
import yaml
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / "ostrawind_dbt"
MODEL = yaml.safe_load((ROOT / "model" / "ostrawind_supply_chain.ossie.yaml").read_text())
TODAY, LAST_Q = "2026-11-20", "Q3 2026 (2026-07-01 to 2026-09-30)"
c = Console(width=int(os.environ.get("ASK_WIDTH", 140)), force_terminal=True, color_system="truecolor")
llm = OpenAI(base_url=os.environ.get("LLM_URL", "http://127.0.0.1:8999/v1"), api_key="local")

# ---------- the semantic layer, as the agent sees it
def fact(metric):
    x = next(m for m in MODEL["metrics"] if m["name"] == metric)
    return re.search(r"(\w+)\.", x["expression"]["sql"]).group(1)
SUPPLIER_DIM = {"purchase_order": ("supplier__supplier_name", "Dimension('supplier__supplier_name')"),
                "shipment": ("purchase_order__supplier__supplier_name", "Dimension('supplier__supplier_name', entity_path=['purchase_order'])")}
catalog = "\n".join(f"- {m['name']}: {m.get('description','')}" + (f" (also: {', '.join(m['ai_context']['synonyms'])})" if m.get('ai_context') else "")
                    for m in MODEL["metrics"] if fact(m["name"]) in SUPPLIER_DIM)

def query_metrics(metrics, grain="quarter", supplier_name=None):
    metrics = [m for m in metrics if any(x["name"] == m for x in MODEL["metrics"])]
    if not metrics: return "No known metrics. Use names from the metric list."
    groups = {}
    for m in metrics: groups.setdefault(fact(m), []).append(m)
    out = []
    for f, ms in groups.items():
        dim, jinja = SUPPLIER_DIM.get(f, (None, None))
        cmd = ["mf", "query", "--metrics", ",".join(ms), "--group-by", f"metric_time__{grain}" + (f",{dim}" if dim else ""),
               "--order", f"metric_time__{grain}", "--start-time", "2026-01-01", "--end-time", "2026-09-30"]
        if supplier_name and dim: cmd += ["--where", "{{ " + jinja + " }} ILIKE '%" + supplier_name.split()[0] + "%'"]
        c.print(f"[#64748b]  $ {' '.join(a if ' ' not in a else repr(a) for a in cmd)}[/]")
        tmp = tempfile.mktemp(suffix=".csv")
        r = subprocess.run(cmd + ["--csv", tmp, "--quiet"], cwd=DBT, capture_output=True, text=True)
        if r.returncode: return "MetricFlow error: " + r.stdout[-400:]
        rows = list(csv.DictReader(open(tmp))); os.remove(tmp)
        t = Table(header_style="bold #34d399", box=None, padding=(0, 2))
        for k in rows[0]: t.add_column(k.replace("metric_time__", "").replace("purchase_order__", ""))
        for row in rows:
            t.add_row(*[(v[:10] if k.startswith("metric_time") else (f"{float(v):.4f}" if v and float(v) < 2 else f"{float(v):,.2f}") if re.match(r"^-?[\d.]+$", v or "") else v) for k, v in row.items()])
        c.print(t)
        def show(k, v):                       # rates as percentages, so the model compares like with like
            if k.startswith("metric_time"): return v[:10]
            if k.endswith("_rate") and v: return f"{float(v) * 100:.1f}%"
            if v and re.match(r"^-?[\d.]+$", v): return f"{float(v):,.2f}"
            return v
        out += [json.dumps({k.replace("metric_time__", "").replace("purchase_order__", ""): show(k, v) for k, v in row.items()}) for row in rows]
    return "\n".join(out)

# ---------- documents: section-level BM25 over docs/*.md
SECTIONS = []; TITLES = {}
for p in sorted((ROOT / "docs").glob("*.md")):
    txt = p.read_text(); doc_id = re.search(r"doc_id: (\S+)", txt).group(1); body = txt.split("---", 2)[2]
    TITLES[doc_id] = re.search(r"title: (.+)", txt).group(1).strip()
    for chunk in re.split(r"\n(?=## |\*\*)", body):
        if chunk.strip(): SECTIONS.append((doc_id, chunk.strip()))
tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())
DF = Counter(w for _, s in SECTIONS for w in set(tok(s))); AVG = sum(len(tok(s)) for _, s in SECTIONS) / len(SECTIONS)
def search_documents(query, k=3):
    q = tok(query); scores = []
    for i, (d, s) in enumerate(SECTIONS):
        tf = Counter(tok(s)); L = sum(tf.values())
        sc = sum(math.log(1 + (len(SECTIONS) - DF[w] + 0.5) / (DF[w] + 0.5)) * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * L / AVG)) for w in q if w in tf)
        scores.append((sc, i))
    hits = [SECTIONS[i] for sc, i in sorted(scores, reverse=True)[:k] if sc > 0]
    for d, s in hits: c.print(f"[#64748b]  [{d}][/] {s.splitlines()[0][:110]}")
    return "\n\n".join(f"[{d}] ({TITLES[d]})\n{s}" for d, s in hits) or "No matching documents."

TOOLS = [
 {"type": "function", "function": {"name": "query_metrics", "description": "Get governed supply chain metrics from the semantic layer (MetricFlow). Returns one row per period and supplier.",
  "parameters": {"type": "object", "properties": {
     "metrics": {"type": "array", "items": {"type": "string"}, "description": "Metric names from the metric list"},
     "grain": {"type": "string", "enum": ["quarter", "month"]},
     "supplier_name": {"type": "string", "description": "Optional supplier name filter, e.g. Pangrove"}}, "required": ["metrics"]}}},
 {"type": "function", "function": {"name": "search_documents", "description": "Search supplier contracts, incident reports and logistics policies. Returns sections with their document id.",
  "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]
SYSTEM = f"""You are a supply chain analyst for Ostrawind Supply Co. Today is {TODAY}. "Last quarter" means {LAST_Q}.
Rules from the semantic model: {MODEL['ai_context']['instructions']}
Use query_metrics for every number (never estimate) and search_documents for contract terms and causes.
For an SLA question: (1) get the supplier's quarterly metrics including purchase_value, and compare each rate with its target
(OTD and fill rate must be at or above target, damage rate at or below); (2) search the documents for the incident report about this supplier (its title names the supplier) and take the cause from it;
(3) search again for service credits and force majeure; (4) compute the credit: the contract gives a flat percentage of the
quarter's purchase_value per missed service level (it does not depend on the size of the shortfall), so
credit = contract percentage x number of missed levels x purchase_value. Take dates and causes only from the incident report
whose title names this supplier; a carrier's incident report is a different event and is not the supplier's breach.
Metrics you can query (by quarter or month, optionally for one supplier):
{catalog}
Final answer: short, with the numbers, the targets, the cause, and what Ostrawind can claim. Cite documents as [DOC-ID] and metrics by name."""

NUM = re.compile(r"(?<![\w-])(?:\d{4}-\d{2}-\d{2}|\$?\d+(?:,\d{3})*(?:\.\d+)?%?)(?![\w-])")
def val(t): return float(t.strip("$%").replace(",", ""))
def check_numbers(answer, evidence):
    """Every number in the answer must come from a tool result, or be simple arithmetic on two of them."""
    found = set()
    for t in NUM.findall(evidence):
        if re.match(r"\d{4}-\d{2}-\d{2}$", t): found.add(t); continue
        v = val(t); found |= {round(v, 2), round(v * 100, 1), round(v * 100, 2)}
    nums = sorted({round(val(t), 2) for t in NUM.findall(evidence) if not re.match(r"\d{4}-", t)})
    t = Table(title="fact check: every number in the answer vs the tool results", header_style="bold #34d399", box=None, padding=(0, 2))
    t.add_column("in the answer"); t.add_column("check")
    ok = bad = 0
    for tok in dict.fromkeys(NUM.findall(answer)):
        if re.match(r"\d{4}-\d{2}-\d{2}$", tok):
            good = tok in found; how = "date in a tool result" if good else "date not in any tool result"
        elif re.fullmatch(r"(19|20)\d\d|\d", tok):
            continue                                   # years and quarter numbers
        else:
            v = round(val(tok), 2); good = v in found; how = "from a tool result" if good else ""
            if not good:
                for a in nums:
                    for b in nums:
                        for op, r in (("x", a * b), ("% of", a * b / 100), ("+", a + b)):
                            if abs(r - v) < 0.011 and a and b: good, how = True, f"= {a:g} {op} {b:,.2f}"; break
                        if good: break
                    if good: break
                if not good: how = "NOT found in any tool result"
            if good: nums = sorted(set(nums) | {v})          # a checked number can feed the next calculation
        ok += good; bad += not good
        t.add_row(tok, f"[#34d399]✓ {how}[/]" if good else f"[bold red]✗ {how}[/]")
    c.print(t)
    c.print(f"[bold {'#34d399' if not bad else 'red'}]{ok} of {ok + bad} numbers grounded.[/]")
    return ok, bad

def ask(question, max_steps=6):
    c.print(Panel(question, title="question", border_style="#34d399", expand=False))
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    t0 = time.time(); calls = 0
    for step in range(max_steps):
        r = llm.chat.completions.create(model="local", messages=msgs, tools=TOOLS, temperature=0, max_tokens=700,
                                     extra_body={"seed": 19, "cache_prompt": False})
        m = r.choices[0].message
        if not m.tool_calls:
            c.print(Panel(Markdown(m.content.strip()), title=f"answer  ·  {calls} tool calls  ·  {time.time()-t0:.0f} s on CPU", border_style="#fbbf24"))
            ok, bad = check_numbers(m.content, "\n".join(x["content"] for x in msgs if x["role"] == "tool"))
            (ROOT / "results").mkdir(exist_ok=True)
            (ROOT / "results" / "agent_last_run.md").write_text(f"# {question}\n\nTool calls: {calls}, {time.time()-t0:.0f} s on CPU, "
                f"numbers grounded: {ok}/{ok + bad}\n\n{m.content.strip()}\n")
            return m.content
        msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [tc.model_dump() for tc in m.tool_calls]})
        for tc in m.tool_calls:
            args = json.loads(tc.function.arguments or "{}"); calls += 1
            c.print(f"[bold #22d3ee]→ {tc.function.name}[/] [#cbd5e1]{json.dumps(args)}[/]")
            res = query_metrics(**args) if tc.function.name == "query_metrics" else search_documents(**args)
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": res})
    c.print("[red]stopped: too many steps[/]")

if __name__ == "__main__":
    ask(" ".join(sys.argv[1:]) or "Did Pangrove breach its SLA last quarter, and why?")
