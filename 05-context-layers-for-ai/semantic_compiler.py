"""Small SQL compiler for an Apache Ossie (incubating) semantic model.

TEACHING HELPER, NOT AN OSSIE FEATURE. It is the compiler from folder 04
(04-semantic-model-with-apache-ossie/semantic_demo.py), plus an optional WHERE
filter written with dataset.field names. Ossie defines how names resolve; it does
not ship a query engine.
"""
from collections import deque

import sqlglot
from sqlglot import exp


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

    def compile(self, metric_refs, by, where=None):
        """where: an optional filter written with dataset.field names (added in folder 05)."""
        dims = [(f, self.field_sql(*f.split("."))) for f in by]
        mets = [(r, self.metric(r)) for r in metric_refs]
        cond = None
        if where:
            cond = self.parse(where).transform(
                lambda n: self.wrap(self.field_sql(n.table, n.name)) if isinstance(n, exp.Column) and n.table else n)
        frm = self.joins()
        sel = ",\n  ".join(f"{self.sql(t)} AS {n.split('.')[-1]}" for n, t in dims + mets)
        sql = f"SELECT\n  {sel}\n{frm}"
        if cond is not None: sql += f"\nWHERE {self.sql(cond)}"
        if dims: sql += "\nGROUP BY " + ", ".join(str(i + 1) for i in range(len(dims))) + "\nORDER BY 1"
        return sql
