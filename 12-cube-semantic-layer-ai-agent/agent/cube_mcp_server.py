"""A small MCP server that puts Cube's semantic layer in front of an AI agent.

Cube's own MCP server is a hosted Cube Cloud feature, so for a fully local setup this file
wraps Cube Core's REST API with the official MCP Python SDK. Two tools:
  describe_model  -> the views, measures and dimensions THIS role may use (Cube /v1/meta)
  query           -> runs a semantic query (Cube /v1/load); Cube writes the SQL and applies
                     the access policies for the role
The role comes from CUBE_ROLE (see cube/roles.json). The agent never sees a token or any SQL.
"""
import calendar
import json
import logging
import os
import re
from typing import Optional

from mcp.server.fastmcp import FastMCP

import cube_client

logging.getLogger("httpx").setLevel(logging.WARNING)
ROLE = os.environ.get("CUBE_ROLE", "exec")
DATA_END = os.environ.get("BANK_DATA_END", "2026-10-31")  # last day in the warehouse
# the time dimension of each view
TIME_DIM = {"balance_sheet": "snapshot_date", "lending": "opened_on", "customer_activity": "transaction_date"}
mcp = FastMCP("kestrel-bay-cube", log_level="WARNING")


@mcp.tool()
def describe_model() -> str:
    """List the views you may query, with every measure and dimension and what it means. Call this first."""
    out = []
    for view in cube_client.meta(ROLE)["cubes"]:
        out.append(f"VIEW {view['name']}: {view.get('description', '').strip()}")
        for m in view["measures"]:
            out.append(f"  measure   {m['name']}: {m.get('description', '')}")
        for d in view["dimensions"]:
            kind = "time dim " if d["type"] == "time" else "dimension"
            out.append(f"  {kind} {d['name']}: {d.get('description', '')}")
    return "\n".join(out)


def period_to_range(period: str) -> list[str]:
    """'2026-10' -> month, '2026-Q3' -> quarter, '2026' -> year, '2026-YTD' -> year to date.
    A period that is still running ends on the last day in the data."""
    start, end = _range(period)
    return [start, min(end, DATA_END)]


def _range(period: str):
    p = period.strip().upper().replace(" ", "")
    if re.fullmatch(r"\d{4}-\d{2}", p):
        y, m = int(p[:4]), int(p[5:])
        return [f"{y}-{m:02d}-01", f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"]
    if re.fullmatch(r"\d{4}-Q[1-4]", p):
        y, q = int(p[:4]), int(p[-1])
        m = q * 3
        return [f"{y}-{m - 2:02d}-01", f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"]
    if re.fullmatch(r"\d{4}-YTD", p):
        return [f"{p[:4]}-01-01", f"{p[:4]}-12-31"]
    if re.fullmatch(r"\d{4}", p):
        return [f"{p}-01-01", f"{p}-12-31"]
    raise ValueError(f"period must look like 2026-10, 2026-Q3, 2026 or 2026-YTD, not {period!r}")


@mcp.tool()
def query(measures: list[str], period: str, dimensions: Optional[list[str]] = None,
          filters: Optional[list[dict]] = None, limit: int = 50) -> str:
    """Run a query on the semantic layer and return the rows as JSON.

    measures: e.g. ["balance_sheet.total_deposits"]
    period: the time the question asks about: "2026-10" (a month), "2026-Q3" (a quarter),
            "2026" (a year) or "2026-YTD" (year to date). The semantic layer knows how each
            measure adds up over time (balances use the period's last month-end).
    dimensions: e.g. ["balance_sheet.region"]
    filters: e.g. [{"member": "balance_sheet.segment", "operator": "equals", "values": ["Small Business"]}]
    """
    q = {"measures": measures, "dimensions": dimensions or [], "limit": limit}
    try:
        view = measures[0].split(".")[0]
        q["timeDimensions"] = [{"dimension": f"{view}.{TIME_DIM[view]}", "dateRange": period_to_range(period)}]
        if filters:
            q["filters"] = filters
        rows = cube_client.load(q, ROLE)["data"]
    except Exception as e:  # access denied, unknown member, bad period: let the agent read why
        return f"ERROR from Cube: {str(e).split(' Please make it visible')[0]}"
    return json.dumps([{k: v for k, v in r.items() if k.split(".")[-1] not in TIME_DIM.values()} for r in rows])


if __name__ == "__main__":
    mcp.run()  # stdio transport
