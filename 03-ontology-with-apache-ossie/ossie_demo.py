"""Apache Ossie (incubating) ontology demo: validate, explain and query.

    python ossie_demo.py validate   # official JSON Schemas + the official validator
    python ossie_demo.py explain    # concepts, IRIs, verbalizations, rules
    python ossie_demo.py query      # walk the ontology, generate SQL via the mapping, run it
    (explain = concepts + verbalize + rules, query = sql + checks, all = everything)

Point OSSIE_REPO at a local clone of https://github.com/apache/ossie
(default: ./ossie). The schemas, the validator and the Python SDK come from it.
SQL generation here is a small teaching example, not an Ossie feature.
"""
import json, os, re, sqlite3, subprocess, sys
from collections import deque
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

HERE = Path(__file__).parent
OSSIE = Path(os.environ.get("OSSIE_REPO", HERE / "ossie")).resolve()
MODELS = HERE / "models"
ONTOLOGY, MODEL, MAPPING = (MODELS / f for f in ("iot.ontology.yaml", "iot.semantic_model.yaml", "iot.mapping.yaml"))
con = Console(width=int(os.environ["DEMO_WIDTH"]) if os.environ.get("DEMO_WIDTH") else None, highlight=False)

def load(p): return yaml.safe_load(Path(p).read_text())
def step(n, title): con.print(f"\n[bold #34D399]{n}[/]  [bold]{title}[/]")

# ---------------------------------------------------------------- validate
SCHEMAS = {"semantic model": "core-spec/ossie-schema.json", "ontology": "ontology/ontology.json",
           "mapping": "ontology/mapping.json"}

def registry() -> Registry:
    """Serve the schemas' raw.githubusercontent.com $refs from the local clone."""
    reg = Registry()
    for rel in SCHEMAS.values():
        doc = json.loads((OSSIE / rel).read_text())
        res = Resource.from_contents(doc)
        reg = reg.with_resources([(f"https://raw.githubusercontent.com/apache/ossie/main/{rel}", res), (doc["$id"], res)])
    return reg

def validate() -> bool:
    step(1, "JSON Schema check (official Ossie schemas, jsonschema Draft 2020-12)")
    reg, ok = registry(), True
    for (kind, rel), path in zip(SCHEMAS.items(), (MODEL, ONTOLOGY, MAPPING)):
        v = Draft202012Validator(json.loads((OSSIE / rel).read_text()), registry=reg)
        errs = sorted(v.iter_errors(load(path)), key=lambda e: list(e.path))
        ok &= not errs
        con.print(f"   {'[green]PASS[/]' if not errs else '[red]FAIL[/]'}  {path.name:<26} vs {rel}")
        for e in errs[:5]: con.print(f"         [red]{'/'.join(map(str, e.path))}: {e.message}[/]")
    step(2, "Official validator: validation/validate.py (names, references, SQL fields)")
    for path, rel in ((MODEL, None), (ONTOLOGY, SCHEMAS["ontology"]), (MAPPING, SCHEMAS["mapping"])):
        cmd = [sys.executable, str(OSSIE / "validation" / "validate.py"), str(path)] + (["--schema", str(OSSIE / rel)] if rel else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok &= r.returncode == 0
        for line in (r.stdout + r.stderr).strip().splitlines():
            con.print("   " + line.replace("Validation PASSED", "[green]Validation PASSED[/]").replace("Validation FAILED", "[red]Validation FAILED[/]"))
    step(3, "Load the semantic model with the official Python SDK (ossie.OssieDocument)")
    from ossie import OssieDocument
    doc = OssieDocument.from_ossie_yaml(MODEL.read_text())
    con.print(f"   model [bold]{doc.name}[/]: " + ", ".join(f"{d.name} ({len(d.fields or [])} fields)" for d in doc.datasets))
    con.print(f"\n[bold]{'[green]All checks passed' if ok else '[red]Some checks failed'}[/][/]")
    return ok

# ---------------------------------------------------------------- explain
def concepts(onto): return {c["concept"]: c for c in onto["ontology"]}

def expand_iri(iri, prefixes):
    p, _, local = iri.partition(":")
    return prefixes[p] + local if p in prefixes and not local.startswith("//") else iri

def sentence(owner, rel):
    """Read a ManyToOne / OneToOne constraint out loud from the first verbalization."""
    v = rel["verbalizes"][0]
    roles = re.findall(r"\{([^}]+)\}", v)
    if not rel.get("multiplicity") or len(roles) != 2: return None
    last = roles[-1]
    nice = last.split(":")[0] + (f" ({last.split(':')[1]})" if ":" in last else "")
    s = "Each " + v.replace("{" + roles[0] + "}", roles[0], 1).replace("{" + last + "}", "at most one " + nice)
    return s + (", and vice versa" if rel["multiplicity"] == "OneToOne" else "")

def explain(parts=("concepts", "verbalize", "rules")):
    onto = load(ONTOLOGY); C = concepts(onto); pre = onto.get("prefixes", {})
    if "concepts" in parts: show_concepts(onto, C, pre)
    if "verbalize" in parts: show_verbalizations(C)
    if "rules" in parts: show_rules(onto, C)

def show_concepts(onto, C, pre):
    step(1, f"Ontology [bold]{onto['name']}[/] (spec {onto['version']})")
    t = Table(box=box.SIMPLE_HEAD, header_style="bold #34D399", pad_edge=False)
    for h in ("Concept", "Type", "Extends", "Identified by", "IRI"): t.add_column(h)
    for name, c in C.items():
        if c["type"] == "EntityType":
            t.add_row(name, "EntityType", ", ".join(c.get("extends", [])), " + ".join(c.get("identify_by", [])),
                      expand_iri(c["iri"], pre) if "iri" in c else "")
    con.print(t)
    vt = [n for n, c in C.items() if c["type"] == "ValueType"]
    con.print("   [bold]ValueTypes:[/] " + ", ".join(f"{n} < {C[n]['extends'][0]}" for n in vt))
    con.print("   [bold]prefixes:[/] " + ", ".join(f"{k}: {v}" for k, v in pre.items()))

def show_verbalizations(C):
    step(2, "Verbalizations: every relationship reads as a sentence")
    for name, c in C.items():
        for r in c.get("relationships", []):
            if r["name"] in c.get("identify_by", []) and c["type"] == "EntityType" and len(c.get("identify_by")) == 1: continue
            tag = "[magenta]derived[/] " if r.get("derived_by") else ""
            con.print(f"   [cyan]{name + '.' + r['name']:<26}[/] {tag}" + "  |  ".join(r["verbalizes"]))
    step(3, "Multiplicity, read out loud")
    for name in ("Sensor", "Site", "SensorReading"):
        for r in C[name].get("relationships", [])[:3]:
            s = sentence(name, r)
            if s: con.print(f"   {s}")

def show_rules(onto, C):
    step(4, "Business rules (requires / derived_by)")
    for name, c in C.items():
        for e in c.get("requires", []): con.print(f"   [yellow]requires[/]   {name}: {e}")
        for e in c.get("derived_by", []): con.print(f"   [magenta]derived_by[/] {name}: {e}")
        for r in c.get("relationships", []):
            for e in r.get("requires", []): con.print(f"   [yellow]requires[/]   {name}.{r['name']}: {e}")
            for e in r.get("derived_by", []): con.print(f"   [magenta]derived_by[/] {name}.{r['name']}: {e}")
    ai = onto.get("ai_context", {})
    step(5, "ai_context for AI tools")
    con.print(f"   instructions: {ai.get('instructions', '')}\n   examples: {ai.get('examples')}")

# ---------------------------------------------------------------- query
def entity_edges(C):
    """Binary relationships between entity types, plus derived ones (first role -> last role)."""
    for name, c in C.items():
        for r in c.get("relationships", []):
            roles = r.get("roles", [])
            if len(roles) == 1 and C.get(roles[0]["concept"], {}).get("type") == "EntityType" and "name" not in roles[0]:
                yield name, r, roles[0]["concept"]

def shortest_path(C, src, dst):
    q, seen = deque([(src, [])]), {src}
    while q:
        node, path = q.popleft()
        if node == dst: return path
        for a, r, b in entity_edges(C):
            if a == node and b not in seen: seen.add(b); q.append((b, path + [(a, r, b)]))

def hops(C, path):
    """Replace a derived relationship by the dot-path in its derived_by rule."""
    out = []
    for a, r, b in path:
        m = re.fullmatch(r"(\w+)((?:\.\w+)+)\((\w+)\)", r["derived_by"][0]) if r.get("derived_by") else None
        if not m: out.append((a, r["name"], b)); continue
        cur = m.group(1)
        for name in m.group(2).strip(".").split("."):
            nxt = next(x["concept"] for x in C[cur]["relationships"] if x["name"] == name for x in [x["roles"][0]])
            out.append((cur, name, nxt)); cur = nxt
    return out

class Mapping:
    def __init__(self, mapping):
        self.cm = {c["concept"]: c for c in mapping["concept_mappings"]}
    def child(self, concept, rel):
        for lm in self.cm[concept].get("link_mappings", []):
            for ch in lm.get("children", []):
                if ch.get("relationship") == rel: return ch["object_mapping"]["expression"]
    def ident(self, concept):
        return self.cm[concept]["object_mappings"][0].get("expression")

def model_relationship(model, left, right):
    (ld, lc), (rd, rc) = left.split("."), right.split(".")
    for r in model.get("relationships", []):
        if {(r["from"], tuple(r["from_columns"])), (r["to"], tuple(r["to_columns"]))} == {(ld, (lc,)), (rd, (rc,))}:
            return r["name"]

def to_sql(expr, M, base):
    """Rewrite Concept.rel references and == into SQL over mapped fields."""
    expr = re.sub(r"\b(\w+)\.(\w+)\b", lambda m: M.child(m.group(1), m.group(2)) or m.group(0), expr)
    return expr.replace("==", "=")

def query(parts=("sql", "checks")):
    onto, model, mapping = load(ONTOLOGY), load(MODEL), load(MAPPING)
    C, M = concepts(onto), Mapping(mapping)
    db = sqlite3.connect(HERE / "data" / "iot.db")
    if "sql" in parts: generate_and_run(C, M, model, db)
    if "checks" in parts: rule_checks(C, mapping, db)

def generate_and_run(C, M, model, db):
    step(1, "Question: average temperature and ALERT readings per customer")
    path = shortest_path(C, "SensorReading", "Customer")
    con.print("   ontology path:  " + "  ->  ".join([path[0][0]] + [f"[cyan]{r['name']}[/] -> {b}" for a, r, b in path]))
    hp = hops(C, path)
    con.print("   derived_by expands it to:  " + "  ->  ".join([hp[0][0]] + [f"[cyan]{r}[/] -> {b}" for a, r, b in hp]))
    step(2, "Mapping + semantic model turn each hop into a join")
    base = M.child("SensorReading", "temperature").split(".")[0]
    joins = []
    for a, r, b in hp:
        left, right = M.child(a, r), M.ident(b)
        rel = model_relationship(model, left, right)
        joins.append(f"JOIN {right.split('.')[0]} ON {left} = {right}")
        con.print(f"   {a + '.' + r:<22} {left:<19} = {right:<22} [dim]via {rel}[/]")
    alert = to_sql(C["AlertReading"]["derived_by"][0], M, base)
    sql = (f"SELECT {M.child('Customer', 'name')} AS customer,\n"
           f"       ROUND(AVG({M.child('SensorReading', 'temperature')}), 2) AS avg_celsius,\n"
           f"       SUM(CASE WHEN {alert} THEN 1 ELSE 0 END) AS alert_readings,\n"
           f"       COUNT(*) AS readings\n"
           f"FROM {base}\n" + "\n".join(joins) + "\nGROUP BY customer\nORDER BY avg_celsius DESC;")
    con.print(Panel(Syntax(sql, "sql", theme="monokai", background_color="default"), title="generated SQL", border_style="#2DD4BF", expand=False))
    cur = db.execute(sql)
    t = Table(box=box.SIMPLE_HEAD, header_style="bold #34D399")
    for d in cur.description: t.add_column(d[0], justify="right" if d[0] != "customer" else "left")
    for row in cur.fetchall(): t.add_row(*map(str, row))
    step(3, "Run it on data/iot.db (SQLite)"); con.print(t)

def rule_checks(C, mapping, db):
    step(4, "Value-type rules become data-quality checks")
    for name, c in C.items():
        if c["type"] != "ValueType" or not c.get("requires"): continue
        col = next((ch["object_mapping"]["expression"] for cm in mapping["concept_mappings"] for lm in cm.get("link_mappings", [])
                    for ch in lm.get("children", []) if ch["object_mapping"].get("concept") == name), None)
        if not col: continue
        cond = " AND ".join("(" + re.sub(r"\b%s\b" % name, col, e).replace("==", "=") + ")" for e in c["requires"])
        bad = db.execute(f"SELECT COUNT(*) FROM {col.split('.')[0]} WHERE NOT ({cond})").fetchone()[0]
        con.print(f"   {name:<12} {cond:<62} violations: [{'green' if bad == 0 else 'red'}]{bad}[/]")
    out = HERE / "out"; out.mkdir(exist_ok=True)
    lines = ["flowchart LR"]
    for a, r, b in entity_edges(C):
        lines.append(f"  {a} -->|{r['name']}{' (derived)' if r.get('derived_by') else ''}| {b}")
    lines += [f"  {n} -.->|extends| {p}" for n, c in C.items() if c["type"] == "EntityType" for p in c.get("extends", [])]
    (out / "iot_ontology.mmd").write_text("\n".join(lines) + "\n")
    con.print(f"\n   wrote out/iot_ontology.mmd ({len(lines) - 1} edges, Mermaid)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    ok = True
    if cmd in ("validate", "all"): ok = validate()
    if cmd in ("explain", "all"): explain()
    if cmd in ("concepts", "verbalize", "rules"): explain((cmd,))
    if cmd in ("query", "all"): query()
    if cmd in ("sql", "checks"): query((cmd,))
    sys.exit(0 if ok else 1)
