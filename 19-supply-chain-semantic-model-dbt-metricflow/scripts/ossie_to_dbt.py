"""Turn an Apache Ossie semantic model into a dbt project that MetricFlow can query.

  python scripts/ossie_to_dbt.py model/ostrawind_supply_chain.ossie.yaml ostrawind_dbt

What maps to what:
  Ossie dataset       -> a thin dbt model + a MetricFlow semantic model
  primary_key         -> primary entity (named after the dataset)
  relationship        -> foreign entity on the "from" dataset (named after the "to" dataset)
  field               -> dimension (time or categorical); its SQL expression is kept
  metric AGG(ds.f)    -> measure on ds + simple metric
  metric A / B        -> two measures + a ratio metric
  ai_context synonyms -> meta.synonyms, so tools and agents can find them
"""
import re, sys, json
from pathlib import Path
import yaml

AGG = {"SUM": "sum", "COUNT": "count", "AVG": "average", "MIN": "min", "MAX": "max"}
TERM = re.compile(r"^\s*(SUM|COUNT|AVG|MIN|MAX)\(\s*(\w+)\.(\w+)\s*\)\s*$", re.I)

def main(src, out):
    m = yaml.safe_load(Path(src).read_text())
    out = Path(out)
    (out / "models" / "ossie").mkdir(parents=True, exist_ok=True)
    (out / "models" / "semantic").mkdir(parents=True, exist_ok=True)
    ds = {d["name"]: d for d in m["datasets"]}
    fields = {(d["name"], f["name"]): f for d in m["datasets"] for f in d["fields"]}

    # 1. sources + one thin model per dataset
    schema = {d["source"].split(".")[0] for d in m["datasets"]}.pop()
    (out / "models" / "sources.yml").write_text(yaml.safe_dump({"version": 2, "sources": [{
        "name": schema, "schema": schema,
        "tables": [{"name": d["source"].split(".")[1], "description": d.get("description", "")} for d in m["datasets"]]}]},
        sort_keys=False))
    for d in m["datasets"]:
        table = d["source"].split(".")[1]
        (out / "models" / "ossie" / f"{d['name']}.sql").write_text(
            f"-- Ossie dataset: {d['name']}\nselect * from {{{{ source('{schema}', '{table}') }}}}\n")

    # 2. measures and metrics from the Ossie metrics
    measures = {name: [] for name in ds}
    seen, metrics = set(), []
    def measure(term):
        agg, dset, fld = TERM.match(term).groups()
        f = fields[(dset, fld)]
        name = f"{fld}_{AGG[agg.upper()]}"
        if (dset, name) not in seen:
            seen.add((dset, name))
            measures[dset].append({"name": name, "agg": AGG[agg.upper()], "expr": f["expression"]["sql"]})
        return name
    simple_for = {}
    def simple_metric(mname, label=None, desc=None, meta=None):
        if mname in simple_for: return simple_for[mname]
        metrics.append({"name": mname, "label": label or mname.replace("_", " "), "description": desc or f"Helper for {mname}.",
                        "type": "simple", "type_params": {"measure": mname}, **({"config": {"meta": meta}} if meta else {})})
        simple_for[mname] = mname
        return mname
    for x in m["metrics"]:
        sql = x["expression"]["sql"]
        meta = {"synonyms": x.get("ai_context", {}).get("synonyms", [])}
        parts = sql.split("/")
        if len(parts) == 1:
            meas = measure(sql)
            metrics.append({"name": x["name"], "label": x["name"].replace("_", " "), "description": x.get("description", ""),
                            "type": "simple", "type_params": {"measure": meas}, "config": {"meta": meta}})
        else:
            num, den = (simple_metric(measure(p)) for p in parts)
            metrics.append({"name": x["name"], "label": x["name"].replace("_", " "), "description": x.get("description", ""),
                            "type": "ratio", "type_params": {"numerator": num, "denominator": den}, "config": {"meta": meta}})
    # simple helper metrics must not clash with real metric names
    names = [mt["name"] for mt in metrics]
    assert len(names) == len(set(names)), "metric name clash"

    # 3. semantic models
    sms = []
    for d in m["datasets"]:
        pk = d["primary_key"][0]
        entities = [{"name": d["name"], "type": "primary", "expr": pk}]
        for r in m.get("relationships", []):
            if r["from"] == d["name"]:
                entities.append({"name": r["to"], "type": "foreign", "expr": r["from_columns"][0]})
        dims, time_dims = [], []
        for f in d["fields"]:
            if f["expression"]["sql"] in [e["expr"] for e in entities]:
                continue                                   # keys are entities, not dimensions
            dim = {"name": f["name"], "expr": f["expression"]["sql"], "description": f.get("description", "")[:200]}
            if f.get("dimension", {}).get("is_time"):
                dim.update(type="time", type_params={"time_granularity": "day"}); time_dims.append(f["name"])
            else:
                dim["type"] = "categorical"
            dims.append(dim)
        sm = {"name": d["name"], "description": d.get("description", ""), "model": f"ref('{d['name']}')",
              "config": {"meta": {"synonyms": d.get("ai_context", {}).get("synonyms", [])}},
              "entities": entities, "dimensions": dims}
        if measures[d["name"]]:
            sm["defaults"] = {"agg_time_dimension": time_dims[0]}   # first time field in the dataset
            sm["measures"] = measures[d["name"]]
        sms.append(sm)

    sem = {"version": 2, "semantic_models": sms, "metrics": metrics}
    (out / "models" / "semantic" / "ossie_semantic_models.yml").write_text(
        "# Generated from the Apache Ossie model by scripts/ossie_to_dbt.py. Do not edit by hand.\n" +
        yaml.safe_dump(sem, sort_keys=False, width=120))
    # model-level ai_context travels with the project for agents
    (out / "ossie_ai_context.json").write_text(json.dumps({"name": m["name"], "instructions": m["ai_context"]["instructions"],
        "examples": m["ai_context"].get("examples", [])}, indent=2))
    n_meas = sum(len(v) for v in measures.values())
    print(f"semantic models: {len(sms)}  entities: {sum(len(s['entities']) for s in sms)}  "
          f"dimensions: {sum(len(s['dimensions']) for s in sms)}  measures: {n_meas}  "
          f"metrics: {len(m['metrics'])} (+{len(metrics) - len(m['metrics'])} helper)")

if __name__ == "__main__":
    main(*sys.argv[1:3])
