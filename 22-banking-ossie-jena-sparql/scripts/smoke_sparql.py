#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Assert SPARQL fixtures against Fuseki (and local RDFS inference check)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from rdflib import RDF, RDFS, Graph, Namespace

ROOT = Path(__file__).resolve().parents[1]


def _wait_ready(base: str, timeout: float = 90.0) -> None:
    ping = f"{base.rstrip('/')}/$/ping"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(ping, timeout=2)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError(f"Fuseki not ready at {ping}")


def _run_sparql(
    endpoint: str, query: str, user: str, password: str
) -> dict[str, Any] | bool:
    r = requests.post(
        endpoint,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        auth=(user, password),
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    # ASK may be preceded by PREFIX declarations.
    if isinstance(data, dict) and "boolean" in data:
        return bool(data.get("boolean"))
    return data


def _binding_map(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in row.items():
        if isinstance(v, dict):
            out[k] = str(v.get("value", ""))
        else:
            out[k] = str(v)
    return out


def check_local_rdfs(ttl: Path) -> None:
    """Prove subclass entailment offline (OpenSuspiciousActivity → SuspiciousActivity)."""
    g = Graph()
    g.parse(ttl, format="turtle")
    ns = Namespace("https://example.com/happn-bank#")
    open_cls = ns.OpenSuspiciousActivity
    sus_cls = ns.SuspiciousActivity
    if (open_cls, RDFS.subClassOf, sus_cls) not in g:
        raise AssertionError("missing OpenSuspiciousActivity rdfs:subClassOf SuspiciousActivity")

    opens = list(g.subjects(RDF.type, open_cls))
    if not opens:
        raise AssertionError("expected OpenSuspiciousActivity individuals")
    # Open SARs are also typed SuspiciousActivity (ABox) + subclass axiom in T-box.
    for ind in opens:
        if (ind, RDF.type, sus_cls) not in g:
            raise AssertionError(f"{ind} should also be typed SuspiciousActivity")
    parents = list(g.objects(ns.NonPerformingLoan, RDFS.subClassOf))
    if not parents:
        raise AssertionError("NonPerformingLoan missing rdfs:subClassOf")
    npl = list(g.subjects(RDF.type, ns.NonPerformingLoan))
    if len(npl) < 1:
        raise AssertionError("expected NonPerformingLoan individuals")
    print("ok  local RDFS/OWL subclass checks passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:3030")
    parser.add_argument("--dataset", default="happn")
    parser.add_argument("--user", default=os.environ.get("FUSEKI_USER", "admin"))
    parser.add_argument("--password", default=os.environ.get("FUSEKI_PASSWORD", "admin"))
    parser.add_argument(
        "--checks",
        type=Path,
        default=ROOT / "checks" / "expected_sparql.json",
    )
    parser.add_argument("--ttl", type=Path, default=ROOT / "rdf" / "banking.ttl")
    parser.add_argument("--skip-fuseki", action="store_true")
    args = parser.parse_args()

    if args.ttl.is_file():
        check_local_rdfs(args.ttl)
    else:
        print(f"warn: no TTL at {args.ttl}; skip local RDFS check")

    if args.skip_fuseki:
        return 0

    _wait_ready(args.base)
    endpoint = f"{args.base.rstrip('/')}/{args.dataset}/sparql"
    doc = json.loads(args.checks.read_text(encoding="utf-8"))
    failed = 0
    for q in doc.get("queries") or []:
        qid = q.get("id", "?")
        sparql = q.get("sparql") or ""
        print(f"== {qid} ==")
        try:
            result = _run_sparql(endpoint, sparql, args.user, args.password)
        except Exception as exc:  # noqa: BLE001 — surface endpoint errors
            print(f"  FAIL request: {exc}")
            failed += 1
            continue

        if "expect_ask" in q:
            ok = bool(result) == bool(q["expect_ask"])
            print(f"  ASK → {result} (expected {q['expect_ask']})")
            if not ok:
                failed += 1
            continue

        if not isinstance(result, dict):
            print(f"  FAIL unexpected result type: {type(result)}")
            failed += 1
            continue

        bindings = [_binding_map(b) for b in result.get("results", {}).get("bindings", [])]
        if "expect_count_min" in q:
            # COUNT query: one row with ?c
            count_val = 0
            if bindings:
                raw = bindings[0].get("c") or bindings[0].get("count") or "0"
                count_val = int(float(raw))
            print(f"  count={count_val} (min {q['expect_count_min']})")
            if count_val < int(q["expect_count_min"]):
                failed += 1
            continue

        min_rows = int(q.get("expect_min_rows") or 0)
        print(f"  rows={len(bindings)} (min {min_rows})")
        if len(bindings) < min_rows:
            failed += 1
            continue
        for expected in q.get("expect_bindings") or []:
            if not any(all(row.get(k) == str(v) for k, v in expected.items()) for row in bindings):
                print(f"  FAIL missing binding {expected}")
                failed += 1

    if failed:
        print(f"error: {failed} SPARQL check(s) failed", file=sys.stderr)
        return 1
    print("ok  all SPARQL checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
