"""Tiny semantic-layer compiler: metric + dimensions -> SQL for DuckDB.
OUR OWN TEACHING HELPER for this lesson, not a product or standard feature."""
import re, yaml, pathlib

HERE = pathlib.Path(__file__).parent

def load(path=HERE / "semantic_layer" / "bikeshare_semantic.yaml"):
    return yaml.safe_load(open(path))

def metric_sql(model, name, _seen=()):
    """Expand a metric into one SQL expression. Base metrics get their filter as FILTER (WHERE ...);
    derived metrics reference other metrics by name."""
    if name in _seen: raise ValueError(f"metric cycle at {name}")
    m = model["metrics"][name]; expr = m["expr"]
    names = [n for n in model["metrics"] if re.search(rf"\b{n}\b", expr) and n != name]
    if names:                                              # derived metric
        for n in sorted(names, key=len, reverse=True):
            expr = re.sub(rf"\b{n}\b", "(" + metric_sql(model, n, _seen + (name,)) + ")", expr)
        return expr
    f = m.get("filter")
    if f: expr += f" FILTER (WHERE {f.format(as_of=model['as_of'])})"
    return expr

def compile_query(model, metric, by=()):
    used = {d.split(".")[0] for d in [model["dimensions"][b]["expr"] for b in by]}
    sel = [f"{model['dimensions'][b]['expr']} AS {b}" for b in by]
    m = metric_sql(model, metric)
    m = m.replace(") / (", ")\n         / (")                       # one line per base metric
    if model["metrics"][metric].get("format") == "$0.00": m = f"ROUND({m}, 2)"
    sel.append(f"{m} AS {metric}")
    sql = "SELECT " + ",\n       ".join(sel) + f"\nFROM {model['datasets']['trips']['table']} AS trips"
    for j in model["joins"]:
        ds = j["to"].split(".")[0]
        if ds in used:
            sql += f"\nLEFT JOIN {model['datasets'][ds]['table']} AS {ds} ON {j['from']} = {j['to']}"
    if by: sql += "\nGROUP BY " + ", ".join(map(str, range(1, len(by) + 1))) + "\nORDER BY 1"
    return sql
