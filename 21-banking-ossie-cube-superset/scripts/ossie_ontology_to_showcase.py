#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile OSSIE ontology business conditions into showcase artifacts.

Reads ``ossie/ontology.yaml`` (+ semantic metrics) and writes:

1. ``superset/ontology_rules.md`` — Markdown catalog for Superset
2. ``cube/model/banking_violations.yml`` — Cube measures for compilable ``requires``
3. ``checks/expected_ossie_kpis.json`` — expected KPI values keyed by OSSIE metric names
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("error: PyYAML required", file=sys.stderr)
    sys.exit(1)

# requires expressions we can compile into ClickHouse violation measures.
# Keyed by concept name → (cube, measure_name, sql, type, description)
COMPILABLE: dict[str, dict[str, Any]] = {
    "OpenAccountDepositRule": {
        "cube": "bank_account",
        "name": "closed_account_balance",
        "sql": "balance",
        "type": "sum",
        "filters": [{"sql": "{CUBE}.status = 'closed'"}],
        "description": "Balances on accounts failing open-status deposit rule.",
    },
    "NPLClassificationRule": {
        "cube": "loan",
        "name": "npl_book_principal",
        "sql": "principal",
        "type": "sum",
        "filters": [{"sql": "{CUBE}.npl_flag OR {CUBE}.days_past_due >= 90"}],
        "description": "Principal in the NPL population (flag or days_past_due ≥ 90).",
    },
    "LargeExposureApprovalRule": {
        "cube": "loan",
        "name": "large_exposure_principal",
        "sql": "principal",
        "type": "sum",
        "filters": [{"sql": "{CUBE}.principal >= 300000000"}],
        "description": "Principal on loans at/above the large-exposure threshold.",
    },
}


def _load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def render_markdown(onto: dict[str, Any], semantic: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Happn banking — ontology business conditions",
        "",
        "Definitions below come from the Apache OSSIE `ontology.yaml` package",
        f"(model `{onto.get('name')}`). Superset does **not** run an OWL reasoner;",
        "these conditions are catalogued for operators and compiled into Cube",
        "violation measures where SQL is portable.",
        "",
    ]
    ai = onto.get("ai_context") or {}
    if ai.get("instructions"):
        lines += ["## Package AI context", "", str(ai["instructions"]).strip(), ""]
    if ai.get("synonyms"):
        lines += ["**Synonyms:** " + ", ".join(str(s) for s in ai["synonyms"]), ""]

    metrics = semantic.get("metrics") or []
    if metrics:
        lines += ["## OSSIE metrics (semantic model)", ""]
        for m in metrics:
            lines.append(f"- **{m.get('name')}** — {m.get('description') or ''}".rstrip())
            expr = (m.get("expression") or {}).get("sql")
            if expr:
                lines.append(f"  - SQL: `{ ' '.join(str(expr).split()) }`")
        lines.append("")

    lines += ["## Concepts with requires / derived_by", ""]
    for comp in onto.get("ontology") or []:
        requires = comp.get("requires") or []
        derived = comp.get("derived_by") or []
        ann = comp.get("annotations") or {}
        ai_c = ann.get("ai_context") or {}
        if not (requires or derived or ann.get("policy_rule") or ai_c.get("instructions")):
            continue
        lines.append(f"### {comp.get('concept')}")
        if comp.get("description"):
            lines.append("")
            lines.append(str(comp["description"]).strip())
        if comp.get("extends"):
            lines.append("")
            lines.append("**Extends:** " + ", ".join(comp["extends"]))
        if requires:
            lines.append("")
            lines.append("**requires:**")
            for expr in requires:
                lines.append(f"- `{expr}`")
        if derived:
            lines.append("")
            lines.append("**derived_by:**")
            for expr in derived:
                lines.append(f"- `{expr}`")
        if ann.get("policy_rule"):
            lines.append("")
            lines.append("**policy_rule:**")
            lines.append("```json")
            lines.append(json.dumps(ann["policy_rule"], indent=2, ensure_ascii=False))
            lines.append("```")
        if ai_c.get("instructions"):
            lines.append("")
            lines.append(f"*AI instructions:* {ai_c['instructions']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def violation_measures(onto: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """cube_name → list of Cube measure dicts compiled from ontology requires."""
    by_cube: dict[str, list[dict[str, Any]]] = {}
    concepts = {c.get("concept") for c in onto.get("ontology") or []}
    for concept, spec in COMPILABLE.items():
        if concept not in concepts:
            continue
        measure = {
            "name": spec["name"],
            "title": spec["name"].replace("_", " ").title(),
            "description": spec["description"] + f" (from OSSIE concept {concept})",
            "sql": spec["sql"],
            "type": spec["type"],
        }
        if spec.get("filters"):
            measure["filters"] = spec["filters"]
        by_cube.setdefault(spec["cube"], []).append(measure)
    return by_cube


def _measure_fragment(measure: dict[str, Any]) -> str:
    """Serialize one Cube measure without re-dumping the whole cube file.

    Re-dumping official ossie-cube YAML unquotes ``{CUBE.field}`` into a YAML
    flow map and Cube then fails with ``Unexpected input … null``.
    """
    lines = [
        f"  - name: {measure['name']}",
        f"    title: {measure.get('title') or measure['name']}",
    ]
    desc = measure.get("description") or ""
    if desc:
        lines.append(f"    description: {json.dumps(desc)}")
    lines.append(f"    sql: {measure['sql']}")
    lines.append(f"    type: {measure['type']}")
    filters = measure.get("filters") or []
    if filters:
        lines.append("    filters:")
        for filt in filters:
            sql = str(filt.get("sql") or "")
            lines.append(f'    - sql: "{sql}"')
    return "\n".join(lines) + "\n"


def merge_violations_into_cube_model(
    model_dir: Path, onto: dict[str, Any]
) -> list[str]:
    """Append ontology violation measures into official ossie-cube cube YAML files.

    Ontology is outside Cube's OSSIE converter; this is a showcase compile only.
    Appends measure YAML text only — never re-serializes the official file.
    """
    cubes_dir = model_dir / "cubes" if (model_dir / "cubes").is_dir() else model_dir
    if not cubes_dir.is_dir():
        raise SystemExit(
            f"Cube model missing (run ossie_to_cube.py / ossie-cube export first): {model_dir}"
        )
    by_cube = violation_measures(onto)
    added: list[str] = []
    for cube_name, extras in by_cube.items():
        path = cubes_dir / f"{cube_name}.yml"
        if not path.is_file():
            path = cubes_dir / f"{cube_name}.yaml"
        if not path.is_file():
            print(f"warn: no cube file for {cube_name}; skip violations", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8")
        for measure in extras:
            marker = f"name: {measure['name']}"
            if marker in text:
                added.append(f"{cube_name}.{measure['name']} (exists)")
                continue
            if not text.endswith("\n"):
                text += "\n"
            text += _measure_fragment(measure)
            added.append(f"{cube_name}.{measure['name']}")
        path.write_text(text, encoding="utf-8")
    return added


def expected_kpis_from_seed(data_dir: Path) -> dict[str, Any]:
    """Compute expected values from CSVs using the same filters as OSSIE metrics."""
    import csv

    accounts = list(csv.DictReader((data_dir / "accounts.csv").open(encoding="utf-8")))
    loans = list(csv.DictReader((data_dir / "loans.csv").open(encoding="utf-8")))
    txns = list(csv.DictReader((data_dir / "transactions.csv").open(encoding="utf-8")))

    def _truthy(value: str | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "t", "yes"}

    total_deposits = sum(
        float(r["balance"]) for r in accounts if r.get("status") == "open"
    )
    total_principal = sum(float(r["principal"]) for r in loans)
    npl_principal = sum(
        float(r["principal"]) for r in loans if _truthy(r.get("npl_flag"))
    )
    npl_ratio = npl_principal / total_principal if total_principal else 0.0
    transaction_volume = sum(abs(float(r["amount"])) for r in txns)

    return {
        "description": (
            "Expected KPI values derived from OSSIE metric definitions applied to "
            "the demo CSVs in data/ (not adapter constants)."
        ),
        "tolerance": 0.0001,
        "source": "ossie/semantic_model.yaml metrics + seed CSVs",
        "kpis": {
            "total_deposits": {
                "cube": "bank_account",
                "measure": "total_deposits",
                "expected": total_deposits,
            },
            "npl_principal": {
                "cube": "loan",
                "measure": "npl_principal",
                "expected": npl_principal,
            },
            "total_loan_principal": {
                "cube": "loan",
                "measure": "total_principal",
                "expected": total_principal,
            },
            "npl_ratio": {
                "cube": "loan",
                "measure": "npl_ratio",
                "expected": npl_ratio,
            },
            "transaction_volume": {
                "cube": "transaction",
                "measure": "transaction_volume",
                "expected": transaction_volume,
            },
        },
    }


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", type=Path, default=here / "ossie" / "ontology.yaml")
    parser.add_argument(
        "--semantic", type=Path, default=here / "ossie" / "semantic_model.yaml"
    )
    parser.add_argument("--data", type=Path, default=here / "data")
    parser.add_argument(
        "--markdown-out", type=Path, default=here / "superset" / "ontology_rules.md"
    )
    parser.add_argument(
        "--cube-model",
        type=Path,
        default=here / "cube" / "model",
        help="Cube model dir (official ossie-cube output) to merge violation measures into",
    )
    parser.add_argument(
        "--expected-out",
        type=Path,
        default=here / "checks" / "expected_ossie_kpis.json",
    )
    args = parser.parse_args()

    onto = _load(args.ontology)
    semantic = _load(args.semantic)
    if not isinstance(onto, dict) or not isinstance(semantic, dict):
        print("error: invalid OSSIE documents", file=sys.stderr)
        return 1

    md = render_markdown(onto, semantic)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.write_text(md, encoding="utf-8")
    print(f"wrote {os.path.relpath(args.markdown_out)}")

    added = merge_violations_into_cube_model(args.cube_model, onto)
    print(f"merged violation measures into {os.path.relpath(args.cube_model)}: {', '.join(added) or '(none)'}")

    expected = expected_kpis_from_seed(args.data)
    args.expected_out.parent.mkdir(parents=True, exist_ok=True)
    args.expected_out.write_text(
        json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # Keep legacy filename in sync for smoke_kpis.py.
    legacy = here / "checks" / "expected_kpis.json"
    legacy.write_text(
        json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {os.path.relpath(args.expected_out)} (and {legacy.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
