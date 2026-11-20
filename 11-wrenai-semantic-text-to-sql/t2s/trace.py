"""Run one question through one arm and print each step as it happens."""
import asyncio, json, time
from rich.console import Console
from rich.syntax import Syntax
from rich.markup import escape
from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.usage import UsageLimits
from . import arms, config

console = Console(force_terminal=True, color_system="truecolor", width=150, highlight=False)
COLOR = {"raw": "#f59e0b", "raw+": "#60a5fa", "wren": "#34d399"}
TITLE = {"raw": "RAW text-to-SQL (DDL only)", "raw+": "RAW+ text-to-SQL (DDL + sample values)", "wren": "WrenAI semantic layer"}


def _short(text, n=220):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + " ..."


async def _run(arm: str, question: str, quiet: bool):
    agent = arms.wren_agent() if arm == "wren" else arms.raw_agent(with_values=arm == "raw+")
    steps = []
    calls, last_ok = {}, {"sql": None}

    async def on_event(ctx, events):
        async for ev in events:
            if isinstance(ev, FunctionToolCallEvent):
                args = ev.part.args_as_dict() if hasattr(ev.part, "args_as_dict") else ev.part.args
                steps.append(ev.part.tool_name)
                if ev.part.tool_name in ("run_sql", "wren_query", "wren_dry_plan"):
                    calls[ev.part.tool_call_id] = args.get("sql")
                if not quiet:
                    a = args.get("sql") or args.get("question") or json.dumps(args)
                    console.print(f"[bold {COLOR[arm]}]{arm} >[/] [bold]{ev.part.tool_name}[/]  " + escape(_short(a, 170)))
            elif isinstance(ev, FunctionToolResultEvent):
                ok = type(ev.result).__name__ == "ToolReturnPart"
                if ok and calls.get(ev.result.tool_call_id):
                    # the last SQL that ran (or, for Wren, planned) without error is the one we score
                    last_ok["sql"] = calls[ev.result.tool_call_id]
                if quiet:
                    continue
                content = getattr(ev.result, "content", "")
                console.print("   " + escape(_short(content, 200)), style="dim")

    t = time.time()
    try:
        result = await agent.run(question, event_stream_handler=on_event,
                                 usage_limits=UsageLimits(request_limit=config.MAX_REQUESTS))
        return last_ok["sql"], result.output, steps, time.time() - t, None
    except Exception as e:
        # Same rule for both arms: if the model runs out of budget or fails to finish,
        # we still score the last SQL that ran successfully (if any).
        if last_ok["sql"]:
            return last_ok["sql"], "(did not finish)", steps, time.time() - t, type(e).__name__
        raise


def ask(arm: str, question: str, quiet: bool = False) -> dict:
    if not quiet:
        console.print(f"[bold {COLOR[arm]}]{TITLE[arm]}[/]  [bold]Q: " + escape(question) + "[/]")
    try:
        sql, text, steps, secs, note = asyncio.run(_run(arm, question, quiet))
        rec = {"arm": arm, "question": question, "sql": sql, "answer": text, "steps": steps, "seconds": round(secs, 1), "note": note}
    except Exception as e:
        rec = {"arm": arm, "question": question, "sql": None, "answer": None, "error": f"{type(e).__name__}: {str(e)[:200]}", "steps": [], "seconds": None}
    if not quiet:
        if rec["sql"] or rec.get("answer"):
            if rec["sql"]:
                console.print(Syntax(rec["sql"], "sql", theme="monokai", word_wrap=True, background_color="default"))
            console.print(f"[bold]{arm} answer:[/] " + escape(rec["answer"]))
        else:
            console.print(f"[bold red]no answer:[/] {rec.get('error')}")
    return rec
