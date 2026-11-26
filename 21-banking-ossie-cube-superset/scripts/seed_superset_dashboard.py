#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seed a Happn banking KPI dashboard into local Superset.

Creates virtual datasets against Cube SQL API, KPI charts, and one dashboard.
Idempotent: reuses existing assets by name when present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    print("error: requests required", file=sys.stderr)
    sys.exit(1)

DASHBOARD_TITLE = "Happn Banking — Apache OSSIE definitions"
DB_NAME = "Cube SQL API"
HERE = Path(__file__).resolve().parent.parent
ONTOLOGY_MD = HERE / "superset" / "ontology_rules.md"

# Virtual datasets: SQL is Cube SQL dialect (MEASURE / GROUP BY).
DATASETS: list[dict[str, Any]] = [
    {
        "table_name": "kpi_total_deposits",
        "sql": (
            "SELECT MEASURE(total_deposits) AS total_deposits "
            "FROM bank_account"
        ),
        "columns": [{"column_name": "total_deposits", "type": "FLOAT", "is_dttm": False}],
        "metrics": [
            {
                "metric_name": "total_deposits",
                "expression": "MAX(total_deposits)",
                "metric_type": None,
                "verbose_name": "Total Deposits",
            }
        ],
    },
    {
        "table_name": "kpi_npl",
        "sql": (
            "SELECT MEASURE(npl_ratio) AS npl_ratio, "
            "MEASURE(npl_principal) AS npl_principal, "
            "MEASURE(total_principal) AS total_principal "
            "FROM loan"
        ),
        "columns": [
            {"column_name": "npl_ratio", "type": "FLOAT", "is_dttm": False},
            {"column_name": "npl_principal", "type": "FLOAT", "is_dttm": False},
            {"column_name": "total_principal", "type": "FLOAT", "is_dttm": False},
        ],
        "metrics": [
            {
                "metric_name": "npl_ratio",
                "expression": "MAX(npl_ratio)",
                "verbose_name": "NPL Ratio",
            },
            {
                "metric_name": "npl_principal",
                "expression": "MAX(npl_principal)",
                "verbose_name": "NPL Principal",
            },
            {
                "metric_name": "total_principal",
                "expression": "MAX(total_principal)",
                "verbose_name": "Total Loan Principal",
            },
        ],
    },
    {
        "table_name": "kpi_txn_volume",
        "sql": (
            "SELECT MEASURE(transaction_volume) AS transaction_volume "
            "FROM transaction"
        ),
        "columns": [
            {"column_name": "transaction_volume", "type": "FLOAT", "is_dttm": False},
        ],
        "metrics": [
            {
                "metric_name": "transaction_volume",
                "expression": "MAX(transaction_volume)",
                "verbose_name": "Transaction Volume",
            },
        ],
    },
    {
        "table_name": "kpi_deposits_by_branch",
        "sql": (
            "SELECT branch_id, MEASURE(total_deposits) AS total_deposits "
            "FROM bank_account GROUP BY 1"
        ),
        "columns": [
            {"column_name": "branch_id", "type": "STRING", "is_dttm": False},
            {"column_name": "total_deposits", "type": "FLOAT", "is_dttm": False},
        ],
        "metrics": [
            {
                "metric_name": "total_deposits",
                "expression": "MAX(total_deposits)",
                "verbose_name": "Total Deposits",
            }
        ],
    },
    {
        "table_name": "kpi_loans_by_branch",
        "sql": (
            "SELECT branch_id, MEASURE(total_principal) AS loan_principal "
            "FROM loan GROUP BY 1"
        ),
        "columns": [
            {"column_name": "branch_id", "type": "STRING", "is_dttm": False},
            {"column_name": "loan_principal", "type": "FLOAT", "is_dttm": False},
        ],
        "metrics": [
            {
                "metric_name": "loan_principal",
                "expression": "MAX(loan_principal)",
                "verbose_name": "Loan Principal",
            }
        ],
    },
    {
        "table_name": "kpi_deposits_by_customer",
        "sql": (
            "SELECT customer_id, MEASURE(total_deposits) AS total_deposits "
            "FROM bank_account GROUP BY 1"
        ),
        "columns": [
            {"column_name": "customer_id", "type": "STRING", "is_dttm": False},
            {"column_name": "total_deposits", "type": "FLOAT", "is_dttm": False},
        ],
        "metrics": [
            {
                "metric_name": "total_deposits",
                "expression": "MAX(total_deposits)",
                "verbose_name": "Total Deposits",
            }
        ],
    },
    {
        "table_name": "kpi_closed_account_balance",
        "sql": (
            "SELECT MEASURE(closed_account_balance) AS closed_account_balance "
            "FROM bank_account"
        ),
        "columns": [
            {
                "column_name": "closed_account_balance",
                "type": "FLOAT",
                "is_dttm": False,
            }
        ],
        "metrics": [
            {
                "metric_name": "closed_account_balance",
                "expression": "MAX(closed_account_balance)",
                "verbose_name": "Closed Account Balance",
            }
        ],
    },
    {
        "table_name": "kpi_npl_book",
        "sql": (
            "SELECT MEASURE(npl_book_principal) AS npl_book_principal, "
            "MEASURE(large_exposure_principal) AS large_exposure_principal "
            "FROM loan"
        ),
        "columns": [
            {"column_name": "npl_book_principal", "type": "FLOAT", "is_dttm": False},
            {
                "column_name": "large_exposure_principal",
                "type": "FLOAT",
                "is_dttm": False,
            },
        ],
        "metrics": [
            {
                "metric_name": "npl_book_principal",
                "expression": "MAX(npl_book_principal)",
                "verbose_name": "NPL Book Principal",
            },
            {
                "metric_name": "large_exposure_principal",
                "expression": "COALESCE(MAX(large_exposure_principal), 0)",
                "verbose_name": "Large Exposure Principal",
            },
        ],
    },
]


class SupersetClient:
    def __init__(self, base: str, username: str, password: str) -> None:
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.username = username
        self.password = password
        self.token = ""
        self.csrf = ""

    def login(self) -> None:
        r = self.session.post(
            f"{self.base}/api/v1/security/login",
            json={
                "username": self.username,
                "password": self.password,
                "provider": "db",
                "refresh": True,
            },
            timeout=30,
        )
        r.raise_for_status()
        self.token = r.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        csrf = self.session.get(f"{self.base}/api/v1/security/csrf_token/", timeout=30)
        csrf.raise_for_status()
        self.csrf = csrf.json()["result"]
        self.session.headers.update(
            {
                "X-CSRFToken": self.csrf,
                "Referer": self.base,
            }
        )

    def get(self, path: str, **kwargs: Any) -> Any:
        r = self.session.get(f"{self.base}{path}", timeout=60, **kwargs)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        r = self.session.post(f"{self.base}{path}", json=payload, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"POST {path} → {r.status_code}: {r.text}")
        return r.json()

    def put(self, path: str, payload: dict[str, Any]) -> Any:
        r = self.session.put(f"{self.base}{path}", json=payload, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"PUT {path} → {r.status_code}: {r.text}")
        return r.json()

    def find_one(self, resource: str, column: str, value: str) -> dict[str, Any] | None:
        # Rison filter
        q = (
            f"(filters:!((col:{column},opr:eq,value:'{value}')),"
            f"page:0,page_size:10)"
        )
        data = self.get(f"/api/v1/{resource}/", params={"q": q})
        rows = data.get("result") or []
        return rows[0] if rows else None


def ensure_database(client: SupersetClient) -> dict[str, Any]:
    row = client.find_one("database", "database_name", DB_NAME)
    if not row:
        raise SystemExit(
            f"database {DB_NAME!r} not found — start the stack with ./run-local.sh first"
        )
    # Ensure SQL Lab + CTAS-friendly flags.
    detail = client.get(f"/api/v1/database/{row['id']}")
    result = detail["result"]
    patch = {
        "database_name": result["database_name"],
        "sqlalchemy_uri": result.get("sqlalchemy_uri")
        or "postgresql+psycopg2://cube:cube@cube:15432/db",
        "expose_in_sqllab": True,
        "allow_ctas": True,
        "allow_cvas": True,
        "allow_dml": False,
        "extra": json.dumps(
            {
                "allows_virtual_table_explore": True,
                "cost_estimate_enabled": False,
            }
        ),
    }
    client.put(f"/api/v1/database/{row['id']}", patch)
    return {"id": row["id"], "uuid": row.get("uuid")}


def ensure_dataset(
    client: SupersetClient, database_id: int, spec: dict[str, Any]
) -> dict[str, Any]:
    existing = client.find_one("dataset", "table_name", spec["table_name"])
    if existing:
        ds_id = existing["id"]
    else:
        created = client.post(
            "/api/v1/dataset/",
            {
                "database": database_id,
                "schema": "public",
                "table_name": spec["table_name"],
                "sql": spec["sql"],
            },
        )
        ds_id = created["id"]

    # Refresh columns from SQL, then attach metrics.
    try:
        client.put(f"/api/v1/dataset/{ds_id}/refresh", {})
    except RuntimeError:
        # Some builds use POST for refresh.
        r = client.session.post(
            f"{client.base}/api/v1/dataset/{ds_id}/refresh",
            timeout=60,
        )
        if r.status_code >= 400:
            print(f"  warn: dataset refresh failed for {spec['table_name']}: {r.text[:200]}")

    detail = client.get(f"/api/v1/dataset/{ds_id}")["result"]
    # Dataset PUT accepts a narrow column schema — strip read-only fields.
    raw_columns = detail.get("columns") or []
    columns: list[dict[str, Any]] = []
    for c in raw_columns:
        columns.append(
            {
                "id": c.get("id"),
                "column_name": c["column_name"],
                "type": c.get("type") or "STRING",
                "is_dttm": bool(c.get("is_dttm")),
                "filterable": bool(c.get("filterable", True)),
                "groupby": bool(c.get("groupby", True)),
                "expression": c.get("expression") or "",
                "verbose_name": c.get("verbose_name"),
                "description": c.get("description"),
            }
        )
    if not columns:
        columns = [
            {
                "column_name": c["column_name"],
                "type": c.get("type") or "STRING",
                "is_dttm": False,
                "filterable": True,
                "groupby": True,
            }
            for c in spec["columns"]
        ]
    existing_metrics = {
        m["metric_name"]: m for m in (detail.get("metrics") or []) if m.get("metric_name")
    }
    metrics = []
    for m in spec["metrics"]:
        row: dict[str, Any] = {
            "metric_name": m["metric_name"],
            "expression": m["expression"],
            "verbose_name": m.get("verbose_name") or m["metric_name"],
            "metric_type": m.get("metric_type"),
        }
        prior = existing_metrics.get(m["metric_name"])
        if prior and prior.get("id") is not None:
            row["id"] = prior["id"]
        metrics.append(row)
    owner_ids = [
        o["id"] if isinstance(o, dict) else int(o) for o in (detail.get("owners") or [])
    ]
    client.put(
        f"/api/v1/dataset/{ds_id}",
        {
            "database_id": database_id,
            "table_name": spec["table_name"],
            "sql": spec["sql"],
            "columns": columns,
            "metrics": metrics,
            "owners": owner_ids,
        },
    )
    detail = client.get(f"/api/v1/dataset/{ds_id}")["result"]
    metric_map = {m["metric_name"]: m["id"] for m in (detail.get("metrics") or []) if "id" in m}
    column_map = {
        c["column_name"]: c["id"] for c in (detail.get("columns") or []) if "id" in c
    }
    return {
        "id": ds_id,
        "datasource": f"{ds_id}__table",
        "metrics": metric_map,
        "columns": column_map,
        "table_name": spec["table_name"],
    }


def _query_context(
    dataset_id: int, params: dict[str, Any], *, viz_type: str = ""
) -> dict[str, Any]:
    if viz_type == "markdown" or params.get("markup_type") == "markdown":
        return {
            "datasource": {"id": dataset_id, "type": "table"},
            "force": False,
            "queries": [],
            "form_data": params,
            "result_format": "json",
            "result_type": "full",
        }
    metrics = params.get("metrics") or (
        [params["metric"]] if "metric" in params else []
    )
    columns: list[str] = []
    if params.get("x_axis"):
        columns.append(str(params["x_axis"]))
    for col in params.get("groupby") or []:
        if col not in columns:
            columns.append(col)
    return {
        "datasource": {"id": dataset_id, "type": "table"},
        "force": False,
        "queries": [
            {
                "metrics": metrics,
                "columns": columns,
                "filters": [],
                "row_limit": params.get("row_limit", 1000),
            }
        ],
        "form_data": params,
        "result_format": "json",
        "result_type": "full",
    }


def _big_number_params(metric: str) -> dict[str, Any]:
    return {
        "metric": metric,
        "adhoc_filters": [],
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": ",.2f",
        "time_format": "smart_date",
    }


def _bar_params(metric: str, x_axis: str) -> dict[str, Any]:
    # Superset 4 echarts bar needs `x_axis` (categorical). Plain `groupby`
    # alone triggers a frontend "Unexpected error" on the dashboard.
    return {
        "metrics": [metric],
        "x_axis": x_axis,
        "groupby": [],
        "adhoc_filters": [],
        "row_limit": 100,
        "show_legend": False,
        "y_axis_format": ",.0f",
        "x_axis_title": x_axis,
        "y_axis_title": metric,
        "orientation": "vertical",
        "color_scheme": "supersetColors",
        "xAxisForceCategorical": True,
        "truncateXAxis": True,
        "showValue": True,
    }


def ensure_chart(
    client: SupersetClient,
    *,
    name: str,
    viz_type: str,
    dataset: dict[str, Any],
    params: dict[str, Any],
    description: str,
) -> int:
    existing = client.find_one("chart", "slice_name", name)
    body = {
        "slice_name": name,
        "viz_type": viz_type,
        "datasource_id": dataset["id"],
        "datasource_type": "table",
        "params": json.dumps(params),
        "query_context": json.dumps(
            _query_context(dataset["id"], params, viz_type=viz_type)
        ),
        "description": description,
    }
    if existing:
        client.put(f"/api/v1/chart/{existing['id']}", body)
        return int(existing["id"])
    created = client.post("/api/v1/chart/", body)
    return int(created["id"])


def ensure_dashboard(
    client: SupersetClient,
    chart_ids: dict[str, int],
    *,
    ontology_markdown: str,
) -> int:
    existing = client.find_one("dashboard", "slug", "happn-banking-kpis")
    if not existing:
        existing = client.find_one("dashboard", "dashboard_title", DASHBOARD_TITLE)

    def chart_block(key: str, chart_id: int, width: int, height: int) -> dict[str, Any]:
        return {
            "type": "CHART",
            "id": chart_id,
            "children": [],
            "meta": {
                "chartId": chart_id,
                "width": width,
                "height": height,
                "sliceName": key,
                "uuid": f"chart-{chart_id}",
            },
        }

    # Row 1: OSSIE metrics · Row 2: ontology Markdown · Row 3: condition outcomes · Row 4: pivots
    positions: dict[str, Any] = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {
            "type": "GRID",
            "id": "GRID_ID",
            "children": [
                "ROW-kpi",
                "ROW-ontology",
                "ROW-violations",
                "ROW-branch",
                "ROW-customer",
            ],
        },
        "HEADER_ID": {
            "type": "HEADER",
            "id": "HEADER_ID",
            "meta": {"text": DASHBOARD_TITLE},
        },
        "ROW-kpi": {
            "type": "ROW",
            "id": "ROW-kpi",
            "children": [
                "CHART-deposits",
                "CHART-npl",
                "CHART-volume",
            ],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        },
        "ROW-ontology": {
            "type": "ROW",
            "id": "ROW-ontology",
            "children": ["MARKDOWN-ontology"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        },
        "ROW-violations": {
            "type": "ROW",
            "id": "ROW-violations",
            "children": [
                "CHART-closed",
                "CHART-npl-book",
                "CHART-large-exp",
            ],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        },
        "ROW-branch": {
            "type": "ROW",
            "id": "ROW-branch",
            "children": ["CHART-dep-branch", "CHART-loan-branch"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        },
        "ROW-customer": {
            "type": "ROW",
            "id": "ROW-customer",
            "children": ["CHART-concentration"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        },
        "CHART-deposits": {
            **chart_block("Total Deposits", chart_ids["Total Deposits"], 4, 26),
            "id": "CHART-deposits",
        },
        "CHART-npl": {
            **chart_block("NPL Ratio", chart_ids["NPL Ratio"], 4, 26),
            "id": "CHART-npl",
        },
        "CHART-volume": {
            **chart_block("Transaction Volume", chart_ids["Transaction Volume"], 4, 26),
            "id": "CHART-volume",
        },
        # Native dashboard MARKDOWN node (not viz_type=markdown chart — that
        # path has no datasource and renders "Unexpected error" in Superset 4).
        "MARKDOWN-ontology": {
            "type": "MARKDOWN",
            "id": "MARKDOWN-ontology",
            "children": [],
            "meta": {
                "code": ontology_markdown,
                "width": 12,
                "height": 80,
            },
        },
        "CHART-closed": {
            **chart_block(
                "Closed Account Balance",
                chart_ids["Closed Account Balance"],
                4,
                26,
            ),
            "id": "CHART-closed",
        },
        "CHART-npl-book": {
            **chart_block("NPL Book Principal", chart_ids["NPL Book Principal"], 4, 26),
            "id": "CHART-npl-book",
        },
        "CHART-large-exp": {
            **chart_block(
                "Large Exposure Principal",
                chart_ids["Large Exposure Principal"],
                4,
                26,
            ),
            "id": "CHART-large-exp",
        },
        "CHART-dep-branch": {
            **chart_block(
                "Deposits by Branch", chart_ids["Deposits by Branch"], 6, 50
            ),
            "id": "CHART-dep-branch",
        },
        "CHART-loan-branch": {
            **chart_block(
                "Loan Principal by Branch",
                chart_ids["Loan Principal by Branch"],
                6,
                50,
            ),
            "id": "CHART-loan-branch",
        },
        "CHART-concentration": {
            **chart_block(
                "Customer Deposit Concentration",
                chart_ids["Customer Deposit Concentration"],
                12,
                50,
            ),
            "id": "CHART-concentration",
        },
    }

    body = {
        "dashboard_title": DASHBOARD_TITLE,
        "slug": "happn-banking-kpis",
        "published": True,
        "json_metadata": json.dumps(
            {
                "timed_refresh_immune_slices": [],
                "expanded_slices": {},
                "refresh_frequency": 0,
                "color_scheme": "supersetColors",
                "label_colors": {},
                "shared_label_colors": {},
                "color_scheme_domain": [],
                "cross_filters_enabled": True,
            }
        ),
        "position_json": json.dumps(positions),
        "certified_by": "Apache OSSIE model",
        "certification_details": (
            "Definitions from Apache OSSIE (metrics + ontology requires); "
            "Cube/Superset are presentation only."
        ),
    }
    if existing:
        client.put(f"/api/v1/dashboard/{existing['id']}", body)
        dash_id = int(existing["id"])
    else:
        created = client.post("/api/v1/dashboard/", body)
        dash_id = int(created["id"])

    # Link charts → dashboard via each chart's `dashboards` relation (Superset 4).
    for name, chart_id in chart_ids.items():
        detail = client.get(f"/api/v1/chart/{chart_id}")["result"]
        params = detail.get("params") or "{}"
        if isinstance(params, dict):
            params = json.dumps(params)
        qc_raw = detail.get("query_context") or "{}"
        qc = json.loads(qc_raw) if isinstance(qc_raw, str) else (qc_raw or {})
        ds_id = int((qc.get("datasource") or {}).get("id") or 0)
        if not ds_id:
            raise RuntimeError(f"chart {name!r} missing datasource id in query_context")
        client.put(
            f"/api/v1/chart/{chart_id}",
            {
                "slice_name": detail["slice_name"],
                "description": detail.get("description"),
                "viz_type": detail["viz_type"],
                "datasource_id": ds_id,
                "datasource_type": "table",
                "params": params,
                "query_context": qc_raw if isinstance(qc_raw, str) else json.dumps(qc),
                "dashboards": [dash_id],
                "owners": [
                    o["id"] if isinstance(o, dict) else int(o)
                    for o in (detail.get("owners") or [])
                ],
            },
        )
    return dash_id


def wait_ready(base: str, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            r = requests.get(f"{base.rstrip('/')}/health", timeout=3)
            if r.status_code == 200:
                return
            last = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(2)
    raise SystemExit(f"Superset not ready ({last})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8088")
    parser.add_argument("--user", default=os.environ.get("SUPERSET_USER", "admin"))
    parser.add_argument("--password", default=os.environ.get("SUPERSET_PASSWORD", "admin"))
    args = parser.parse_args()

    wait_ready(args.base)
    client = SupersetClient(args.base, args.user, args.password)
    client.login()
    print("logged in to Superset")

    db = ensure_database(client)
    print(f"database id={db['id']} ({DB_NAME})")

    datasets: dict[str, dict[str, Any]] = {}
    for spec in DATASETS:
        ds = ensure_dataset(client, db["id"], spec)
        datasets[spec["table_name"]] = ds
        print(f"  dataset {spec['table_name']} id={ds['id']}")

    ontology_md = (
        ONTOLOGY_MD.read_text(encoding="utf-8")
        if ONTOLOGY_MD.is_file()
        else (
            "# Ontology rules missing\n\n"
            "Run `scripts/ossie_ontology_to_showcase.py` first."
        )
    )
    chart_specs = [
        (
            "Total Deposits",
            "big_number_total",
            datasets["kpi_total_deposits"],
            _big_number_params("total_deposits"),
            "OSSIE metric total_deposits (open account balances).",
        ),
        (
            "NPL Ratio",
            "big_number_total",
            datasets["kpi_npl"],
            {
                **_big_number_params("npl_ratio"),
                "y_axis_format": ".2%",
            },
            "OSSIE metric npl_ratio.",
        ),
        (
            "Transaction Volume",
            "big_number_total",
            datasets["kpi_txn_volume"],
            _big_number_params("transaction_volume"),
            "OSSIE metric transaction_volume.",
        ),
        (
            "Closed Account Balance",
            "big_number_total",
            datasets["kpi_closed_account_balance"],
            _big_number_params("closed_account_balance"),
            "Violation measure from OpenAccountDepositRule.",
        ),
        (
            "NPL Book Principal",
            "big_number_total",
            datasets["kpi_npl_book"],
            _big_number_params("npl_book_principal"),
            "Violation measure from NPLClassificationRule.",
        ),
        (
            "Large Exposure Principal",
            "big_number_total",
            datasets["kpi_npl_book"],
            _big_number_params("large_exposure_principal"),
            "Violation measure from LargeExposureApprovalRule.",
        ),
        (
            "Deposits by Branch",
            "echarts_timeseries_bar",
            datasets["kpi_deposits_by_branch"],
            _bar_params("total_deposits", "branch_id"),
            "OSSIE total_deposits pivoted by branch.",
        ),
        (
            "Loan Principal by Branch",
            "echarts_timeseries_bar",
            datasets["kpi_loans_by_branch"],
            _bar_params("loan_principal", "branch_id"),
            "OSSIE total_principal pivoted by branch.",
        ),
        (
            "Customer Deposit Concentration",
            "echarts_timeseries_bar",
            datasets["kpi_deposits_by_customer"],
            _bar_params("total_deposits", "customer_id"),
            "OSSIE total_deposits by customer (concentration).",
        ),
    ]

    chart_ids: dict[str, int] = {}
    for name, viz, ds, params, desc in chart_specs:
        cid = ensure_chart(
            client,
            name=name,
            viz_type=viz,
            dataset=ds,
            params=params,
            description=desc,
        )
        chart_ids[name] = cid
        print(f"  chart {name!r} id={cid}")

    dash_id = ensure_dashboard(client, chart_ids, ontology_markdown=ontology_md)
    url = f"{args.base.rstrip('/')}/superset/dashboard/{dash_id}/"
    print(f"ok  dashboard id={dash_id}")
    print(f"open {url}")
    print(f"slug  {args.base.rstrip('/')}/superset/dashboard/happn-banking-kpis/")


if __name__ == "__main__":
    main()
