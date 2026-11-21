"""Ask Kestrel Bay Bank a question through Cube, via MCP, with a local model.

  python agent/ask.py "What is the delinquency rate in each region?"            # as an executive
  python agent/ask.py --role prairies_mgr "What is the delinquency rate in each region?"

The model talks to any OpenAI-compatible server: AGENT_BASE_URL (default llama.cpp on :8999).
"""
import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits
from rich.console import Console
from rich.markup import escape

HERE = Path(__file__).resolve().parent
BASE_URL = os.environ.get("AGENT_BASE_URL", "http://127.0.0.1:8999/v1")
API_KEY = os.environ.get("AGENT_API_KEY", "local")
con = Console(highlight=False, width=int(os.environ.get("ASK_WIDTH", "110")))

INSTRUCTIONS = """You answer questions about Kestrel Bay Bank using ONLY the tools of the Cube semantic layer.
The data runs from 2025-01-01 to 2026-10-31; treat 'now' as 2026-10-31.
First call describe_model, then call query with the exact member names it lists.
Give the time the question asks about as period, e.g. "2026-10", "2026-Q3", "2026" or "2026-YTD".
If Cube returns an error saying a member is hidden, you are not allowed to see it: say so plainly and do not guess.
Answer only the question asked, with the numbers from the query result, then stop."""


def model_name():
    name = os.environ.get("AGENT_MODEL")
    if name:
        return name
    with urllib.request.urlopen(BASE_URL.rstrip("/") + "/models", timeout=10) as r:
        return json.load(r)["data"][0]["id"]


async def run(question: str, role: str = "exec", show: bool = True):
    """Run one question. Returns (answer, rows of the last successful query)."""
    server = MCPServerStdio(sys.executable, [str(HERE / "cube_mcp_server.py")],
                            env={**os.environ, "CUBE_ROLE": role}, cwd=str(HERE), timeout=30)
    model = OpenAIChatModel(model_name(), provider=OpenAIProvider(base_url=BASE_URL, api_key=API_KEY),
                            settings=ModelSettings(temperature=0, max_tokens=700))
    agent = Agent(model, instructions=INSTRUCTIONS, toolsets=[server])
    say = con.print if show else (lambda *a, **k: None)
    say(f"[bold]role:[/] [magenta]{role}[/]   [bold]question:[/] {escape(question)}")
    last_rows, queried = None, False
    prompt = question
    async with agent:
        for attempt in range(2):
            async with agent.iter(prompt, usage_limits=UsageLimits(request_limit=8)) as run:
                async for node in run:
                    if Agent.is_call_tools_node(node):
                        for part in node.model_response.parts:
                            if part.part_kind == "tool-call":
                                queried |= part.tool_name == "query"
                                a = part.args if isinstance(part.args, str) else json.dumps(part.args)
                                say(f"[cyan]-> MCP {part.tool_name}[/] [dim]{escape(a)}[/]")
                    elif Agent.is_model_request_node(node):
                        for part in node.request.parts:
                            if part.part_kind == "tool-return":
                                text = str(part.content)
                                if part.tool_name == "describe_model":
                                    n = text.count("\n") + 1
                                    say(f"[green]<- {n} lines: views, measures, dimensions[/]")
                                elif text.startswith("ERROR"):
                                    say(f"[red]<- {escape(text[:400])}[/]")
                                else:
                                    last_rows = json.loads(text)
                                    say(f"[green]<- {escape(text[:600])}[/]")
            answer = str(run.result.output).strip()
            if queried or attempt:
                break
            # Guard in code: an answer with no query behind it is not an answer.
            say("[bold red]guard:[/] no query result behind this answer, asking the agent to run the query")
            prompt = (f"{question}\nYou answered without calling the query tool. Call describe_model, then query, "
                      "and answer only from the query result.")
    say(f"[bold yellow]answer:[/] {escape(answer)}")
    return answer, last_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--role", default="exec")
    args = ap.parse_args()
    asyncio.run(run(args.question, args.role))


if __name__ == "__main__":
    main()
