#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate Cube model files from Apache OSSIE using the **official** converter.

This script must NOT re-implement Ossie→Cube translation. It only:

1. Calls ``ossie_cube.convert_ossie_to_cube`` (apache-ossie-cube /
   https://github.com/apache/ossie-converters/tree/main/cube).
2. Applies a thin **warehouse binding**: rewrite ``sql_table`` from the OSSIE
   dataset source name to the demo ClickHouse ``banking.<table>`` tables that
   ``clickhouse/init`` + ``load_clickhouse.sh`` already created.

Cube does not create those tables.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("error: PyYAML required (see requirements.txt)", file=sys.stderr)
    sys.exit(1)

try:
    from ossie_cube import ConversionError, convert_ossie_to_cube
except ImportError:  # pragma: no cover
    print(
        "error: apache-ossie-cube is required.\n"
        "  pip install -e \"git+https://github.com/apache/ossie-converters.git#subdirectory=cube\"\n"
        "  (or: pip install -e /path/to/ossie-converters/cube)",
        file=sys.stderr,
    )
    sys.exit(1)

# Demo ClickHouse database created by clickhouse/init — not invented by Cube.
CH_DATABASE = "banking"

# Last segment of OSSIE dataset `source` → ClickHouse table (already loaded).
SOURCE_TABLE_OVERRIDE: dict[str, str] = {
    "accounts": "accounts",
    "branches": "branches",
    "customers": "customers",
    "loans": "loans",
    "risk_ratings": "risk_ratings",
    "transactions": "transactions",
}

REQUIRED_OSSIE_METRICS = frozenset(
    {
        "total_deposits",
        "total_principal",
        "npl_principal",
        "npl_ratio",
        "transaction_volume",
    }
)


def _bind_sql_table(sql_table: str) -> str:
    """Map the OSSIE dataset source → demo ClickHouse ``banking.<table>``."""
    raw = str(sql_table or "").strip()
    leaf = raw.rsplit(".", 1)[-1]
    table = SOURCE_TABLE_OVERRIDE.get(leaf, leaf)
    return f"{CH_DATABASE}.{table}"


def _rewrite_file_sql_tables(yaml_text: str) -> str:
    """Rewrite ``sql_table`` values only — do not re-dump YAML.

    Re-serializing with PyYAML can inject ``null`` nodes that Cube's YAML
    compiler rejects (``Unexpected input during yaml transpiling: null``).
    Keep the official converter's byte layout intact aside from table binding.
    """

    def repl(match: re.Match[str]) -> str:
        raw = match.group(1).strip().strip("\"'")
        return f"sql_table: {_bind_sql_table(raw)}"

    return re.sub(r"sql_table:\s*([^\n#]+)", repl, yaml_text)


def _assert_metrics_present(semantic: dict[str, Any]) -> None:
    names = {
        str(m.get("name"))
        for m in (semantic.get("metrics") or [])
        if isinstance(m, dict) and m.get("name")
    }
    for ds in semantic.get("datasets") or []:
        for m in ds.get("metrics") or []:
            if isinstance(m, dict) and m.get("name"):
                names.add(str(m["name"]))
    missing = sorted(REQUIRED_OSSIE_METRICS - names)
    if missing:
        raise SystemExit(
            "OSSIE semantic_model is missing required metrics: "
            + ", ".join(missing)
            + ". Fix the OSSIE model, then re-run this script "
            "(official ossie-cube export)."
        )


def render(
    semantic_path: Path,
    out_dir: Path,
    *,
    base_cube: str = "bank_account",
    dialect: str | None = "ANSI_SQL",
) -> None:
    text = semantic_path.read_text(encoding="utf-8")
    semantic = yaml.safe_load(text)
    if not isinstance(semantic, dict):
        raise SystemExit(f"invalid semantic model: {semantic_path}")
    _assert_metrics_present(semantic)

    try:
        files, issues = convert_ossie_to_cube(
            text, dialect=dialect, base_cube=base_cube
        )
    except ConversionError as exc:
        raise SystemExit(f"ossie-cube export failed: {exc}") from exc

    # Wipe previous generated cubes/views so stale homemade YAML cannot linger.
    model_root = out_dir
    for sub in ("cubes", "views"):
        target = model_root / sub
        if target.is_dir():
            for old in target.glob("*.yml"):
                old.unlink()
            for old in target.glob("*.yaml"):
                old.unlink()

    written: list[str] = []
    for rel, content in sorted(files.items()):
        path = model_root / rel
        # Official converter paths are like ``model/cubes/x.yml``; our Cube
        # mount is already ``cube/`` with CUBEJS_SCHEMA_PATH=model, so strip a
        # leading ``model/`` if present when out_dir *is* ``cube/model``.
        parts = Path(rel).parts
        if parts and parts[0] == "model" and model_root.name == "model":
            path = model_root.joinpath(*parts[1:])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_rewrite_file_sql_tables(content), encoding="utf-8")
        written.append(str(path.relative_to(model_root)))

    print(
        f"wrote {len(written)} Cube file(s) via official ossie-cube → {os.path.relpath(model_root)}"
    )
    for name in written:
        print(f"  {name}")
    issue_list = list(issues) if issues is not None else []
    if issue_list:
        print(f"{len(issue_list)} conversion issue(s) from ossie-cube:", file=sys.stderr)
        for issue in issue_list:
            print(f"  {issue}", file=sys.stderr)

    # Fail loud if required demo metrics never landed in any cube measure.
    measure_names: set[str] = set()
    for rel, content in files.items():
        doc = yaml.safe_load(_rewrite_file_sql_tables(content))
        for cube in (doc or {}).get("cubes") or []:
            for m in cube.get("measures") or []:
                if m.get("name"):
                    measure_names.add(str(m["name"]))
    missing_m = sorted(REQUIRED_OSSIE_METRICS - measure_names)
    if missing_m:
        raise SystemExit(
            "official ossie-cube export omitted required measures: "
            + ", ".join(missing_m)
        )


def main() -> None:
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--semantic",
        type=Path,
        default=here / "ossie" / "semantic_model.yaml",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=here / "cube" / "model",
        help="Cube model directory (CUBEJS_SCHEMA_PATH)",
    )
    parser.add_argument("--base-cube", default="bank_account")
    parser.add_argument(
        "--dialect",
        default="ANSI_SQL",
        help="Preferred Ossie expression dialect (ANSI_SQL fallback always applies)",
    )
    args = parser.parse_args()
    if not args.semantic.is_file():
        raise SystemExit(f"missing OSSIE semantic model: {args.semantic}")
    dialect = args.dialect or None
    render(args.semantic, args.out, base_cube=args.base_cube, dialect=dialect)


if __name__ == "__main__":
    main()
