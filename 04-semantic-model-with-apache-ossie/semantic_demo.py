"""Apache Ossie (incubating) semantic model demo: validate, explore and query.

    python semantic_demo.py validate                 # official JSON Schema + validator + Python SDK
    python semantic_demo.py datasets                 # datasets, keys, fields -> source columns
    python semantic_demo.py metrics                  # relationships and both kinds of metrics
    python semantic_demo.py query M1 M2 --by D.F     # compile metrics to SQL and run on DuckDB

Point OSSIE_REPO at a local clone of https://github.com/apache/ossie (default ./ossie).
The schemas, the validator and the Python SDK (pip install ./ossie/python) come from it.

TEACHING HELPER, NOT AN OSSIE FEATURE: the `query` command's SQL compiler below is
written for this lesson. Ossie defines how names resolve; it does not ship a query
engine. The compiler follows the spec's Name Resolution rules (core-spec/spec.md).
"""
import json, os, subprocess, sys
from collections import deque
from pathlib import Path

import duckdb, sqlglot, yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from rich import box
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from sqlglot import exp

HERE = Path(__file__).parent
OSSIE = Path(os.environ.get("OSSIE_REPO", HERE / "ossie")).resolve()
MODELS = HERE / "models"
MODEL, ONTOLOGY, MAPPING = (MODELS / f for f in ("iot.semantic_model.yaml", "iot.ontology.yaml", "iot.mapping.yaml"))
DB = HERE / "data" / "iot.duckdb"
con = Console(width=int(os.environ["DEMO_WIDTH"]) if os.environ.get("DEMO_WIDTH") else None, highlight=False)
MINT = "#34D399"

def load(p): return yaml.safe_load(Path(p).read_text())
def step(n, title): con.print(f"\n[bold {MINT}]{n}[/]  [bold]{title}[/]")

# ------------------------------------------------------------------ validate
SCHEMAS = {"core-spec/ossie-schema.json": MODEL, "ontology/ontology.json": ONTOLOGY, "ontology/mapping.json": MAPPING}

def registry() -> Registry:
    """Serve the schemas' $refs from the local clone instead of the network."""
    reg = Registry()
    for rel in SCHEMAS:
        doc = json.loads((OSSIE / rel).read_text()); res = Resource.from_contents(doc)
        reg = reg.with_resources([(f"https://raw.githubusercontent.com/apache/ossie/main/{rel}", res), (doc["$id"], res)])
    return reg

def validate() -> bool:
    from ossie import OssieDocument, __version__
    step(1, "JSON Schema (official Ossie schemas, Draft 2020-12)")
    reg, ok = registry(), True
    for rel, path in SCHEMAS.items():
        errs = list(Draft202012Validator(json.loads((OSSIE / rel).read_text()), registry=reg).iter_errors(load(path)))
        ok &= not errs
        con.print(f"   {'[green]PASS[/]' if not errs else '[red]FAIL[/]'}  {path.name:<25} vs {rel}")
        for e in errs[:4]: con.print(f"         [red]{'/'.join(map(str, e.path))}: {e.message}[/]")
    step(2, "Official validator (validation/validate.py): names, scoping, SQL")
    for path, rel in ((MODEL, None), (ONTOLOGY, "ontology/ontology.json"), (MAPPING, "ontology/mapping.json")):
        cmd = [sys.executable, str(OSSIE / "validation" / "validate.py"), str(path)] + (["--schema", str(OSSIE / rel)] if rel else [])
        r = subprocess.run(cmd, capture_output=True, text=True); ok &= r.returncode == 0
        for line in (r.stdout + r.stderr).strip().splitlines():
            con.print("   " + line.replace("PASSED", "[green]PASSED[/]").replace("FAILED", "[red]FAILED[/]"))
    step(3, f"Official Python SDK (apache-ossie {__version__}): OssieDocument.from_ossie_yaml")
    doc = OssieDocument.from_ossie_yaml(MODEL.read_text())
    n_ds = sum(len(d.metrics or []) for d in doc.datasets)
    con.print(f"   [bold]{doc.name}[/]: {len(doc.datasets)} datasets, {len(doc.relationships or [])} relationships, "
              f"{n_ds} dataset-scoped + {len(doc.metrics or [])} model-scoped metrics")
    con.print(f"\n[bold]{'[green]All checks passed' if ok else '[red]Some checks failed'}[/][/]")
    return ok

# ------------------------------------------------------------------ explore
def sdk_model():
    from ossie import OssieDocument
    return OssieDocument.from_ossie_yaml(MODEL.read_text())

def datasets():
    m = sdk_model()
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}", title="Fields resolve to source columns", title_style="bold")
    for c in ("dataset", "source", "primary_key", "field", "expression (source columns)", "datatype"): t.add_column(c)
    for d in m.datasets:
        for i, f in enumerate(d.fields or []):
            e = f.expression.sql or ""
            style = "white" if e == f.name else "yellow"
            t.add_row(d.name if i == 0 else "", d.source if i == 0 else "", ", ".join(d.primary_key or []) if i == 0 else "",
                      f.name, f"[{style}]{' '.join(e.split())[:46]}[/]", f.datatype.value if f.datatype else "")
        t.add_section()
    con.print(t)
    con.print("[dim]   yellow = the field name differs from its source expression; keys and joins use FIELD names[/]")
    r = next(f for f in m.datasets[-1].fields if f.name == "reading_hour")
    con.print(f"\n   [bold]reading_hour[/] sql (OSSIE_SQL_2026, authoritative): [cyan]{r.expression.sql}[/]")
    for d in r.expression.dialects or []:
        con.print(f"   [bold]reading_hour[/] dialect {d.dialect}: [cyan]{d.expression}[/]")

def metrics():
    m = sdk_model()
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}", title="Relationships (from = many side, to = one side)", title_style="bold")
    for c in ("name", "from", "from_columns", "to", "to_columns"): t.add_column(c)
    for r in m.relationships or []:
        t.add_row(r.name, r.from_dataset, ", ".join(r.from_columns), r.to, ", ".join(r.to_columns))
    con.print(t)
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}", title="Metrics", title_style="bold")
    for c in ("scope", "referenced as", "expression"): t.add_column(c)
    for d in m.datasets:
        for x in d.metrics or []: t.add_row("dataset", f"{d.name}.{x.name}", x.expression.sql)
    t.add_section()
    for x in m.metrics or []: t.add_row("[yellow]model[/]", x.name, x.expression.sql)
    con.print(t)

# ------------------------------------------------------------------ query (TEACHING HELPER)
class Compiler:
    """Turns Ossie metric references into SQL over the source tables (teaching helper).

    Name resolution follows core-spec/spec.md: field expressions use source columns;
    dataset-scoped metrics use unqualified fields and source.column; model-scoped
    metrics use dataset.field and AGG(dataset.metric). Joins follow relationships
    from the many side to the one side.
    """
    def __init__(self, model):
        self.m = model; self.ds = {d["name"]: d for d in model["datasets"]}
        self.used = set()

    def parse(self, sql): return sqlglot.parse_one(sql)

    @staticmethod
    def wrap(t): return t if isinstance(t, (exp.Column, exp.Literal, exp.Paren)) else exp.Paren(this=t)

    def field_sql(self, ds, field):
        """A field: its expression, whose identifiers are columns of the dataset's source."""
        f = next((f for f in self.ds[ds].get("fields", []) if f["name"] == field), None)
        if f is None: raise KeyError(f"dataset '{ds}' has no field '{field}'")
        self.used.add(ds)
        return self.parse(f["expression"]["sql"]).transform(
            lambda n: exp.column(n.name, table=ds) if isinstance(n, exp.Column) else n)

    def dataset_metric(self, ds, name):
        """Dataset-scoped: unqualified name = field of ds, source.column = source column."""
        x = next((x for x in self.ds[ds].get("metrics", []) if x["name"] == name), None)
        if x is None: raise KeyError(f"dataset '{ds}' has no metric '{name}'")
        self.used.add(ds)
        def fn(n):
            if not isinstance(n, exp.Column): return n
            if n.table.lower() == "source": return exp.column(n.name, table=ds)
            if n.table: raise ValueError(f"{ds}.{name}: qualified reference '{n.sql()}' in a dataset-scoped metric")
            return self.wrap(self.field_sql(ds, n.name))
        return self.parse(x["expression"]["sql"]).transform(fn)

    def model_metric(self, name):
        """Model-scoped: dataset.field, and AGG(dataset.metric) for a dataset-scoped metric."""
        x = next((x for x in self.m.get("metrics", []) if x["name"] == name), None)
        if x is None: raise KeyError(f"no model-scoped metric '{name}'")
        def fn(n):
            if isinstance(n, exp.Agg):
                return exp.Paren(this=self.dataset_metric(n.this.table, n.this.name))
            if isinstance(n, exp.Column):
                if not n.table: raise ValueError(f"{name}: '{n.name}' must be qualified as dataset.field")
                return self.wrap(self.field_sql(n.table, n.name))
            return n
        return self.parse(x["expression"]["sql"]).transform(fn)

    def metric(self, ref):
        return self.dataset_metric(*ref.split(".")) if "." in ref else self.model_metric(ref)

    def joins(self):
        rels = self.m.get("relationships", [])
        def reach(start):                                    # follow many -> one
            seen, q, path = {start}, deque([start]), []
            while q:
                cur = q.popleft()
                for r in rels:
                    if r["from"] == cur and r["to"] not in seen:
                        seen.add(r["to"]); q.append(r["to"]); path.append(r)
            return seen, path
        for base in self.ds:
            seen, path = reach(base)
            if self.used <= seen: break
        else: raise ValueError("no dataset reaches all others through relationships")
        sql = f"FROM {self.ds[base]['source']} AS {base}"
        need = set(self.used) - {base}
        for r in path:
            if not need: break
            on = " AND ".join(f"{self.sql(self.field_sql(r['from'], a))} = {self.sql(self.field_sql(r['to'], b))}"
                              for a, b in zip(r["from_columns"], r["to_columns"]))
            sql += f"\nLEFT JOIN {self.ds[r['to']]['source']} AS {r['to']} ON {on}"
            need.discard(r["to"])
        return sql

    @staticmethod
    def sql(t): return sqlglot.transpile(t.sql(), write="duckdb")[0]

    def compile(self, metric_refs, by):
        dims = [(f, self.field_sql(*f.split("."))) for f in by]
        mets = [(r, self.metric(r)) for r in metric_refs]
        frm = self.joins()
        sel = ",\n  ".join(f"{self.sql(t)} AS {n.split('.')[-1]}" for n, t in dims + mets)
        sql = f"SELECT\n  {sel}\n{frm}"
        if dims: sql += "\nGROUP BY " + ", ".join(str(i + 1) for i in range(len(dims))) + "\nORDER BY 1"
        return sql

def query(args):
    by = []
    if "--by" in args: i = args.index("--by"); by = args[i + 1].split(","); args = args[:i] + args[i + 2:]
    c = Compiler(load(MODEL))
    sql = c.compile(args, by)
    con.print(f"[bold {MINT}]Generated SQL[/] [dim](teaching helper, not an Ossie feature)[/]")
    con.print(Syntax(sql, "sql", theme="monokai", background_color="default", word_wrap=True))
    db = duckdb.connect(str(DB), read_only=True); res = db.execute(sql); cols = [d[0] for d in res.description]
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {MINT}", title="DuckDB result", title_style="bold")
    for col in cols: t.add_column(col, justify="left" if col in [b.split('.')[-1] for b in by] else "right")
    for row in res.fetchall():
        t.add_row(*[f"{v:,.2f}" if isinstance(v, float) else str(v) for v in row])
    con.print(t)

if __name__ == "__main__":
    cmd, rest = (sys.argv[1] if len(sys.argv) > 1 else "validate"), sys.argv[2:]
    if cmd == "validate": sys.exit(0 if validate() else 1)
    elif cmd == "datasets": datasets()
    elif cmd == "metrics": metrics()
    elif cmd == "query": query(rest)
    else: print(__doc__)
