"""The five stages of the data engineering agent. Each stage = a goal, a small tool set, and the shared notes."""
import json
from . import config, lake, guard, trace
from .llm import run, tool_schema, REASON

CONTEXT = ("You are a data engineering agent for Saltmarsh Ferries, a small ferry operator. "
           "Three ticket offices (harbourfront, cedarpoint, gullisland) drop raw CSV exports into lake/raw, "
           "next to a routes.json reference file. You work through tools only. Call one tool at a time and "
           "always fill the reason argument with one short sentence.")

def notes():
    p = config.STATE / "notes.md"
    return p.read_text() if p.exists() else "(no notes yet)"

def S(name, desc, props, required=None):
    return tool_schema(name, desc, {**props, "reason": REASON}, required)

STR = {"type": "string"}

# ------------------------------------------------------------------ 1. discover
def discover():
    trace.stage("discover", "find the raw sources, profile each one, and list the data quality issues")
    profiled = set()
    def profile(name):
        out = lake.profile_source(name); profiled.add(name); return out
    def finish(summary, issues):
        got = {(i.get("file", ""), i.get("column", "")) for i in issues if isinstance(i, dict)}
        exp = lake.expected_findings()
        missing = sorted(f"{f} {c}" for f, c in exp - got)
        extra = sorted(f"{f} {c}" for f, c in got - exp)
        if extra:                                        # ... and nothing the tools did not flag
            raise ValueError("these issues are not backed by any ALERT or DIFFERS line: " + "; ".join(extra) +
                             ". Call finish again with only the flagged issues.")
        if missing:                                      # a deterministic critic: every flagged column must be covered
            raise ValueError("coverage check failed. These flagged file/column pairs are not in your issues: " + "; ".join(missing) +
                             ". Call finish again with ALL issues, the old ones plus these.")
        issues = [i if isinstance(i, str) else f"{i.get('file','?')} | {i.get('column','?')} | {i.get('problem','')}" for i in issues]
        todo = [p.name for p in sorted(config.RAW.iterdir()) if p.suffix in (".csv", ".json") and p.name not in profiled]
        if todo:
            raise ValueError(f"not finished: profile these sources first: {', '.join(todo)}")
        config.STATE.mkdir(exist_ok=True)
        (config.STATE / "notes.md").write_text("# Agent notes: data quality issues found in discover\n" +
                                               "\n".join(f"- {i}" for i in issues) + "\n")
        trace.final("issues found (saved to state/notes.md)", "\n".join(f"- {i}" for i in issues))
        return "saved"
    tools = {
        "list_sources": (S("list_sources", "List the raw files in the lake with row counts and columns.", {}), lake.list_sources),
        "profile_source": (S("profile_source", "Profile one raw file: blanks, distinct counts, value shapes (9=digit, A=upper, a=lower) and top values per column, plus duplicates.",
                             {"name": {"type": "string", "description": "file name from list_sources"}}), profile),
        "compare_files": (S("compare_files", "Compare the value shapes of every column across the ticket files, side by side.", {}), lake.compare_files),
        "finish": (S("finish", "Finish after EVERY source is profiled and the files are compared. Report one issue for every ALERT and every DIFFERS verdict, and nothing the tools did not show.",
                     {"summary": STR, "issues": {"type": "array", "items": {"type": "object", "properties": {
                         "file": {"type": "string", "description": "file name, or 'all ticket files'"}, "column": STR,
                         "problem": {"type": "string", "description": "what is wrong, with the count or example from the profile"}},
                         "required": ["file", "column", "problem"]}}}), finish),
    }
    run(CONTEXT, "Discover the raw sources, profile every one of them (including routes.json), compare the ticket files, then finish with the list of data quality issues you found.", tools)

# ------------------------------------------------------------------ 2. clean
def clean():
    trace.stage("clean", "turn the raw ticket files into one curated table, with a human approving the write")
    fixes = []
    def add_fix(kind, column):
        lake.compile_recipe(fixes + [{"kind": kind, "column": column}])          # validates kind and column
        fixes.append({"kind": kind, "column": column})
        return f"recipe now has {len(fixes)} fixes: " + "; ".join(f"{f['kind']}({f['column']})" for f in fixes)
    def apply_recipe():
        if not fixes:
            raise ValueError("the recipe is empty; add fixes first")
        sql, raw, ok, rej = lake.preview_recipe(fixes)
        details = (f"Create curated.tickets from {raw} raw rows: {ok} clean rows, " +
                   (", ".join(f"{n} rejected ({r})" for r, n in rej) if rej else "0 rejected") +
                   ".\nRejected rows are kept in curated.tickets_rejected, nothing is deleted from lake/raw.")
        ok, fb = guard.approve("write curated.tickets", details, sql, fixes=fixes)
        if not ok:
            return "REJECTED by the human; nothing was written. Their feedback: " + (fb or "(none)") + ". Fix the recipe, then call apply_recipe again."
        n, lo, hi, routes, types = lake.apply_recipe(fixes)
        return f"curated.tickets written: {n} rows, sold_at {lo} .. {hi}, {routes} routes, {types} ticket types. Recipe saved."
    def finish(summary):
        trace.final("clean: done", summary); return "ok"
    kinds = "\n".join(f"- {k}: {v}" for k, v in lake.FIX_KINDS.items())
    system = (CONTEXT + "\n\nYour notes from the discover stage:\n" + notes() +
              f"\n\nColumns in every ticket file: {', '.join(lake.COLUMNS)}.\nFix kinds you can add to the cleaning recipe:\n{kinds}\n"
              "Add one fix per add_fix call. Cover every issue in your notes. Then call apply_recipe once; a human must approve it. Then finish.")
    tools = {
        "add_fix": (S("add_fix", "Add one typed fix to the cleaning recipe.",
                      {"kind": {"type": "string", "enum": list(lake.FIX_KINDS)}, "column": {"type": "string", "enum": lake.COLUMNS}}), add_fix),
        "apply_recipe": (S("apply_recipe", "Dry-run the recipe, show the SQL and row counts to a human, and write curated.tickets only if they approve.", {}), apply_recipe),
        "finish": (S("finish", "Finish with a one-paragraph summary.", {"summary": STR}), finish),
    }
    run(system, "Build the cleaning recipe for the ticket files and apply it.", tools)

# ------------------------------------------------------------------ 3. ask
def ask(question):
    trace.stage("ask", question)
    def run_sql(query):
        trace.sql(query, title="agent SQL (read-only)")
        cols, rows = guard.run_read_only(query)
        return " | ".join(cols) + "\n" + "\n".join(" | ".join(str(v) for v in r) for r in rows)
    def answer(answer, sql):
        trace.final("answer", answer); return "ok"
    system = (CONTEXT + "\n\nCurated tables you can query with DuckDB SQL (read-only):\n" + lake.describe_tables() +
              "\nOne row in curated.tickets is one ticket; fare is its price in CAD. Use the exact values listed above. "
              "Query, check that the result makes sense (a zero or empty result usually means a wrong filter), then call answer.")
    tools = {
        "run_sql": (S("run_sql", "Run ONE read-only DuckDB SELECT and get up to 20 rows back.", {"query": STR}), run_sql),
        "answer": (S("answer", "Give the final answer in one or two sentences with the numbers, plus the SQL you relied on.", {"answer": STR, "sql": STR}), answer),
    }
    run(system, question, tools, finish="answer")

# ------------------------------------------------------------------ 4. checks (data contract)
def checks():
    trace.stage("checks", "write a data contract that every new ticket batch must pass, with a human approving it")
    proposed = []
    def add_check(kind, column="*"):
        if kind not in lake.CHECK_KINDS: raise ValueError(f"unknown check kind {kind}")
        if any(p["kind"] == kind and p["column"] == (None if column == "*" else column) for p in proposed):
            raise ValueError("that check is already proposed")
        if kind not in ("expected_columns", "row_count") and column not in lake.COLUMNS:
            raise ValueError(f"check {kind} needs a column, one of {lake.COLUMNS}")
        proposed.append({"kind": kind, "column": column if kind not in ("expected_columns", "row_count") else None})
        return f"{len(proposed)} checks proposed"
    def save_checks():
        if not proposed: raise ValueError("no checks proposed yet")
        details = "\n".join(f"C{i}  {c['kind']}" + (f"({c['column']})" if c["column"] else "") for i, c in enumerate(proposed, 1))
        ok, fb = guard.approve("save data contract (state/checks.json)", details, checks=proposed)
        if not ok:
            return "REJECTED by the human. Their feedback: " + (fb or "(none)") + ". Adjust the checks, then call save_checks again."
        (config.STATE / "checks.json").write_text(json.dumps(proposed, indent=2)); return f"saved {len(proposed)} checks"
    def finish(summary):
        trace.final("checks: done", summary); return "ok"
    kinds = "\n".join(f"- {k}: {v}" for k, v in lake.CHECK_KINDS.items())
    system = (CONTEXT + "\n\nYour notes from the discover stage:\n" + notes() + f"\n\nCheck kinds:\n{kinds}\n"
              "Propose checks that would catch the issues in your notes, plus schema and volume problems, one add_check per call. "
              "Then call save_checks once; a human must approve it. Then finish.")
    tools = {
        "add_check": (S("add_check", "Propose one check for incoming batches.", {"kind": {"type": "string", "enum": list(lake.CHECK_KINDS)},
                        "column": {"type": "string", "enum": lake.COLUMNS + ["*"], "description": "the column to check; '*' for expected_columns and row_count"}}), add_check),
        "save_checks": (S("save_checks", "Ask the human to approve and save the proposed checks.", {}), save_checks),
        "finish": (S("finish", "Finish with a one-line summary.", {"summary": STR}), finish),
    }
    run(system, "Write the data contract for new ticket batches.", tools)

# ------------------------------------------------------------------ 5. monitor
def monitor():
    trace.stage("monitor", "a new batch landed: check it against the contract, investigate, then accept or quarantine it")
    batches = sorted(p.name for p in config.INCOMING.glob("*.csv")) if config.INCOMING.exists() else []
    if not batches:
        trace.final("monitor", "no incoming batches"); return
    failing = {}                                     # batch -> ids of checks that failed on the last run
    def run_checks(batch):
        res, cols, n = lake.run_checks(batch)
        failing[batch] = [cid for cid, _, _, ok, _ in res if not ok]
        return f"{batch}: {n} rows\n" + "\n".join(f"{cid} {kind}({col}): {'PASS' if ok else 'FAIL'}  {d}" for cid, kind, col, ok, d in res)
    def inspect_failure(batch, check_id):
        return lake.failing_rows(batch, check_id)
    def decide(batch, action, reason_text):
        if action == "accept" and (batch not in failing or failing[batch]):
            # policy guardrail in code, not in the prompt: the model cannot talk its way past a failing contract
            why = "run_checks first" if batch not in failing else f"checks {', '.join(failing[batch])} fail on this batch"
            guard.audit("policy_block", action=f"accept {batch}", why=why)
            return f"BLOCKED by policy: {why}. A batch can only be accepted when every check passes. Quarantine it instead."
        ok, fb = guard.approve(f"{action} {batch}", f"{action} batch {batch}\nreason: {reason_text}", decision=action)
        if not ok:
            return "REJECTED by the human; the batch stays in lake/incoming. Their feedback: " + (fb or "(none)")
        if action == "accept":
            lake.move_batch(batch, "raw"); n = lake.apply_recipe(json.loads((config.STATE / 'recipe.json').read_text()))[0]
            return f"accepted; curated.tickets refreshed to {n} rows"
        lake.move_batch(batch, "quarantine")
        return f"quarantined to lake/quarantine/{batch}; curated.tickets unchanged"
    def accept_batch(batch, why): return decide(batch, "accept", why)
    def quarantine_batch(batch, why): return decide(batch, "quarantine", why)
    def finish(incident_note):
        trace.final("incident note for the data team", incident_note); return "ok"
    B = {"batch": {"type": "string", "enum": batches}}
    tools = {
        "run_checks": (S("run_checks", "Run the saved data contract on an incoming batch.", B), run_checks),
        "inspect_failure": (S("inspect_failure", "Look at sample failing data for one check id like C2.", {**B, "check_id": STR}), inspect_failure),
        "accept_batch": (S("accept_batch", "Merge a batch that passes into the lake (needs human approval).", {**B, "why": STR}), accept_batch),
        "quarantine_batch": (S("quarantine_batch", "Move a failing batch to quarantine (needs human approval).", {**B, "why": STR}), quarantine_batch),
        "finish": (S("finish", "Finish with a short incident note: what failed, the likely cause, and the fix you recommend.", {"incident_note": STR}), finish),
    }
    system = (CONTEXT + "\n\nIncoming batches waiting in lake/incoming: " + ", ".join(batches) +
              "\nRun the checks, inspect each failing check, decide accept or quarantine (a human approves), then finish with an incident note. "
              "In the note, compare the batch columns with the expected ones: a missing column next to a new, similar one usually means a rename.")
    run(system, f"New batch: {batches[0]}. Handle it.", tools)
