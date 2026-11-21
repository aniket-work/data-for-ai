"""GraphQL: the same views as a typed GraphQL schema at /cubejs-api/graphql."""
from rich.syntax import Syntax
from _common import con, rows_table, who, cube_client

gql = """{
  cube(where: {balance_sheet: {snapshot_date: {inDateRange: ["2026-07-01", "2026-09-30"]}}}) {
    balance_sheet(orderBy: {net_interest_income: desc}) {
      region
      net_interest_income
    }
  }
}"""
con.print("[bold]GraphQL[/]  POST http://localhost:4000/cubejs-api/graphql   as", who("exec"))
con.print(Syntax(gql, "graphql", theme="monokai", background_color="#020617"))
res = cube_client.graphql(gql, "exec")
rows_table([r["balance_sheet"] for r in res["data"]["cube"]], "Net interest income, Q3 2026")
