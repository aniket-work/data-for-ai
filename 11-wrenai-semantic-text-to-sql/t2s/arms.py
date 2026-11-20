"""The two arms. Same model, same question, same output shape, same tool budget.

raw  : the model sees only the warehouse DDL and can run read-only SQL on DuckDB.
raw+ : the same, plus 2 sample rows per table and the distinct values of every low-cardinality text column
       (what a schema-aware text-to-SQL tool usually adds). Still no business definitions.
wren : the model works through WrenAI (wren-pydantic toolkit): MDL models, relationships,
       calculated fields, descriptions, business rules and recalled NL->SQL examples.
"""
import duckdb
from pydantic_ai import Agent, ModelRetry
from . import config


# Both arms answer in plain text. The SQL we score is the last query that ran successfully.


def ddl() -> str:
    con = duckdb.connect(str(config.WAREHOUSE), read_only=True)
    out = []
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1").fetchall():
        cols = con.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name=? ORDER BY ordinal_position", [t]).fetchall()
        out.append(f"CREATE TABLE {t} (\n  " + ",\n  ".join(f"{c} {d}" for c, d in cols) + "\n);")
    con.close()
    return "\n".join(out)


def sample_values() -> str:
    con = duckdb.connect(str(config.WAREHOUSE), read_only=True)
    out = []
    for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1").fetchall():
        cur = con.execute(f"SELECT * FROM {t} LIMIT 2")
        cols = [d[0] for d in cur.description]
        out.append(f"-- {t}: sample rows\n-- " + " | ".join(cols) + "\n" + "\n".join("-- " + " | ".join(str(v) for v in r) for r in cur.fetchall()))
        for (c,) in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name=? AND data_type='VARCHAR'", [t]).fetchall():
            vals = con.execute(f"SELECT DISTINCT {c} FROM {t} ORDER BY 1 LIMIT 13").fetchall()
            if len(vals) <= 12:
                out.append(f"-- {t}.{c} values: " + ", ".join(repr(v[0]) for v in vals))
    con.close()
    return "\n".join(out)


def run_raw_sql(sql: str, limit: int = 50):
    con = duckdb.connect(str(config.WAREHOUSE), read_only=True)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchmany(limit)
    finally:
        con.close()


def raw_agent(with_values: bool = False) -> Agent:
    instructions = (
        "You are a data analyst. Answer the business question by writing DuckDB SQL against these tables.\n"
        f"{config.DATA_NOTE}\n\n{ddl()}\n\n" + (sample_values() + "\n\n" if with_values else "") +
        "Call run_sql to execute SQL (you may explore first). Then reply with a one-sentence answer with the numbers.\n" + config.FINISH_NOTE
    )
    agent = Agent(config.llm(), instructions=instructions, output_type=str, retries=2)

    @agent.tool_plain(retries=2)
    def run_sql(sql: str) -> str:
        """Run one read-only DuckDB SELECT and return up to 50 rows."""
        try:
            cols, rows = run_raw_sql(sql)
        except Exception as e:  # the model sees the error and can fix its SQL
            raise ModelRetry(f"SQL error: {str(e).splitlines()[0]}")
        return " | ".join(cols) + "\n" + "\n".join(" | ".join(str(v) for v in r) for r in rows)
    return agent


def wren_toolkit():
    from wren_pydantic import WrenToolkit
    return WrenToolkit.from_project(str(config.WREN_PROJECT))


def wren_rules() -> str:
    rules = sorted((config.WREN_PROJECT / "knowledge" / "rules").glob("*.md"))
    return "\n\n".join(p.read_text().strip() for p in rules)


def wren_agent() -> Agent:
    tk = wren_toolkit()
    toolset = tk.toolset(include_memory_write=False)   # read-only memory: the eval must not teach itself
    instructions = (tk.instructions(toolset=toolset) + f"\n\n## Project rules (knowledge/rules)\n\n{config.DATA_NOTE}\n\n"
                    + wren_rules() + "\n\nWhen done, reply with a one-sentence answer with the numbers.\n" + config.FINISH_NOTE)
    return Agent(config.llm(), instructions=instructions, toolsets=[toolset], output_type=str, retries=2)


def run_final_sql(arm: str, sql: str, limit: int = 50):
    """Execute an arm's final SQL the way that arm runs it (raw: DuckDB; wren: through the MDL)."""
    if arm in ("raw", "raw+"):
        return run_raw_sql(sql, limit)
    table = wren_toolkit().query(sql, limit=limit)
    cols = table.column_names
    return cols, [tuple(r[c] for c in cols) for r in table.to_pylist()]
