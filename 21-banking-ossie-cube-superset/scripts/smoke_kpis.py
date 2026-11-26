#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Query Cube REST API and assert banking KPI values from checks/expected_kpis.json."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    print("error: requests required (see requirements.txt)", file=sys.stderr)
    sys.exit(1)


def wait_ready(base: str, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            r = requests.get(f"{base}/readyz", timeout=3)
            if r.status_code == 200:
                return
            last = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(2)
    raise SystemExit(f"Cube not ready at {base} ({last})")


def load_meta(base: str) -> dict[str, Any]:
    r = requests.get(f"{base}/cubejs-api/v1/meta", timeout=30)
    r.raise_for_status()
    return r.json()


def query_measure(
    base: str,
    cube: str,
    measure: str,
    filters: list[dict[str, Any]] | None = None,
) -> float:
    body: dict[str, Any] = {
        "measures": [f"{cube}.{measure}"],
    }
    if filters:
        body["filters"] = filters
    r = requests.post(f"{base}/cubejs-api/v1/load", json={"query": body}, timeout=60)
    if r.status_code >= 400:
        raise SystemExit(f"Cube query failed ({r.status_code}): {r.text}")
    payload = r.json()
    data = payload.get("data") or []
    if not data:
        raise SystemExit(f"empty result for {cube}.{measure}: {payload}")
    key = f"{cube}.{measure}"
    raw = data[0].get(key)
    if raw is None:
        # Some Cube versions return unprefixed keys.
        raw = data[0].get(measure)
    if raw is None:
        raise SystemExit(f"missing key {key} in {data[0]}")
    return float(raw)


def concentration_check(base: str, here: Path) -> int:
    """Report the largest customer's share of total_deposits against the
    SingleCustomerDepositConcentrationWarning threshold declared in ontology.yaml."""
    import yaml

    onto = yaml.safe_load((here / "ossie" / "ontology.yaml").read_text(encoding="utf-8"))
    threshold = None
    for concept in onto.get("ontology") or []:
        if concept.get("concept") == "SingleCustomerDepositConcentrationWarning":
            rule = (concept.get("annotations") or {}).get("policy_rule") or {}
            threshold = float(rule.get("amount", 0.25))
    if threshold is None:
        return 0
    r = requests.post(
        f"{base}/cubejs-api/v1/load",
        json={"query": {
            "measures": ["bank_account.customer_deposit_share"],
            "dimensions": ["bank_account.customer_id"],
            "order": {"bank_account.customer_deposit_share": "desc"},
        }},
        timeout=60,
    )
    r.raise_for_status()
    rows = r.json().get("data") or []
    total = sum(float(x.get("bank_account.customer_deposit_share") or 0) for x in rows)
    if not rows or not total:
        return 0
    top = rows[0]
    amount = float(top.get("bank_account.customer_deposit_share") or 0)
    share = amount / total
    flag = "WARN" if share > threshold else "ok "
    print(
        f"  {flag} deposit concentration: {top.get('bank_account.customer_id')} holds "
        f"{amount:,.0f} = {share:.1%} of total_deposits (ontology limit {threshold:.0%})"
    )
    return 0  # a policy warning, not a broken KPI


def main() -> None:
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:4000")
    parser.add_argument(
        "--expected",
        type=Path,
        default=here / "checks" / "expected_kpis.json",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    expected_doc = json.loads(args.expected.read_text(encoding="utf-8"))
    tolerance = float(expected_doc.get("tolerance") or 1e-4)
    kpis: dict[str, Any] = expected_doc["kpis"]

    print(f"waiting for Cube at {args.base} …")
    wait_ready(args.base, timeout=args.timeout)
    meta = load_meta(args.base)
    cube_names = {c.get("name") for c in meta.get("cubes") or []}
    print(f"Cube meta: {len(cube_names)} cubes → {sorted(cube_names)}")

    failed = 0
    for name, spec in kpis.items():
        cube = spec["cube"]
        measure = spec["measure"]
        exp = float(spec["expected"])
        filters = spec.get("filters")
        got = query_measure(args.base, cube, measure, filters)
        ok = abs(got - exp) <= max(tolerance, abs(exp) * tolerance)
        mark = "ok " if ok else "FAIL"
        print(f"  {mark} {name}: got={got} expected={exp}")
        if not ok:
            failed += 1

    # Extra: branch deposit ranking (informational).
    r = requests.post(
        f"{args.base}/cubejs-api/v1/load",
        json={
            "query": {
                "measures": ["bank_account.total_deposits"],
                "dimensions": ["bank_account.branch_id"],
                "order": {"bank_account.total_deposits": "desc"},
            }
        },
        timeout=60,
    )
    if r.ok:
        print("  branch deposits:")
        for row in r.json().get("data") or []:
            print(
                f"    {row.get('bank_account.branch_id')}: "
                f"{row.get('bank_account.total_deposits')}"
            )

    # Business condition from ontology.yaml: single-customer deposit concentration.
    failed += concentration_check(args.base, here)

    if failed:
        raise SystemExit(f"{failed} KPI check(s) failed")
    print("ok  all KPI checks passed")


if __name__ == "__main__":
    main()
