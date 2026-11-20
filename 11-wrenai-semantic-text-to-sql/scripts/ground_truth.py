"""Ground truth for eval/questions.yml from the Lesson 10 MetricFlow definitions.

Run with the Lesson 10 environment active (it has `mf`), from this folder:
    python scripts/ground_truth.py            # writes eval/ground_truth.json
It calls `mf query` in ../10-metricflow-banking-metrics/bank_dbt.
"""
import csv, json, os, subprocess, tempfile, yaml
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBT = os.environ.get("BANK_DBT_DIR", os.path.join(HERE, "..", "10-metricflow-banking-metrics", "bank_dbt"))
out = {}
for q in yaml.safe_load(open(os.path.join(HERE, "eval", "questions.yml"))):
    m = q["mf"]; f = tempfile.mktemp(suffix=".csv")
    subprocess.run(["mf", "query", "--metrics", m["metrics"], "--group-by", m["group_by"], "--start-time", m["start"],
                    "--end-time", m["end"], "--csv", f, "--quiet"], cwd=DBT, check=True, capture_output=True)
    rows = list(csv.DictReader(open(f))); os.remove(f)
    if q.get("key"):
        ans = {r[q["key"]]: float(r[q["value"]]) for r in rows if r[q["value"]] not in ("", None)
               and (not q.get("keep") or r[q["key"]] in q["keep"])}
    else:
        ans = float(rows[-1][q["value"]])
    out[q["id"]] = {"question": q["question"], "answer": ans, "kind": q.get("kind", "amount")}
    print(q["id"], q["question"], "->", ans)
json.dump(out, open(os.path.join(HERE, "eval", "ground_truth.json"), "w"), indent=2)
