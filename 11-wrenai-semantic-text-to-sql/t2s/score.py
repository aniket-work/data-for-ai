"""Score an arm's SQL against the MetricFlow ground truth by RUNNING it (never trust the model's prose).

A numeric answer is correct within 0.5% (amounts and counts) or 0.05 points (rates; 0.0525 or 5.25 both accepted).
A filtered question (one expected key) may answer with a single row and no key column.
For a breakdown, every expected row (region, product, segment) must be present with a matching number.
"""
import math
from . import arms


def _nums(row):
    out = []
    for v in row:
        try:
            f = float(v)
            if not math.isnan(f):
                out.append(f)
        except (TypeError, ValueError):
            pass
    return out


def _match(x, truth, kind):
    if kind == "rate":
        return abs(x - truth) <= 0.0005 or abs(x / 100 - truth) <= 0.0005
    return abs(x - truth) <= 0.005 * abs(truth)


def score(arm, sql, truth, kind):
    """Return (verdict, detail, rows)."""
    if not sql:
        return "no answer", "no SQL ran", None
    try:
        cols, rows = arms.run_final_sql(arm, sql)
    except Exception as e:
        return "error", str(e).splitlines()[0][:120], None
    if not rows:
        return "wrong", "0 rows", (cols, rows)
    if isinstance(truth, dict) and len(truth) == 1 and len(rows) == 1:
        # A filtered question ("small-business loans", "new mortgages"): one row is a valid answer,
        # even without the key column, as long as its number matches.
        truth = next(iter(truth.values()))
    if isinstance(truth, dict):
        missing = []
        for key, val in truth.items():
            hit = [r for r in rows if any(str(c).strip().lower() == key.lower() for c in r)]
            if not any(_match(x, val, kind) for r in hit for x in _nums(r)):
                missing.append(key)
        if missing:
            return "wrong", "mismatch: " + ", ".join(missing), (cols, rows)
        return "correct", "", (cols, rows)
    if any(_match(x, truth, kind) for x in _nums(rows[0])):
        return "correct", "", (cols, rows)
    return "wrong", f"got {_nums(rows[0])[:2]}", (cols, rows)
