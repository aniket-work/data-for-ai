"""AI data engineering agent, hands-on (Data for AI, lesson 09).

    python data_agent.py discover          profile the raw files and note the issues
    python data_agent.py clean             build + apply a cleaning recipe (human approves the write)
    python data_agent.py ask "question"    answer with SQL the agent writes (read-only)
    python data_agent.py checks            write a data contract for new batches (human approves)
    python data_agent.py monitor           check a new batch, investigate, accept or quarantine (human approves)
    python data_agent.py reset             delete the warehouse, notes, recipe, checks and audit log
"""
import shutil, sys
from agent import config, stages
from agent.trace import console, audit
from agent.llm import client

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "reset":
        for p in (config.DB, config.STATE):
            if p.is_dir(): shutil.rmtree(p)
            elif p.exists(): p.unlink()
        console.print("reset: warehouse and agent state removed"); return
    if cmd not in ("discover", "clean", "ask", "checks", "monitor"):
        print(__doc__); return
    _, model = client()
    console.print(f"[#64748B]model [bold #E2E8F0]{model.split('/')[-1]}[/] via OpenAI-compatible API at {config.BASE_URL}[/]")
    if cmd == "ask":
        stages.ask(" ".join(sys.argv[2:]) or "Which route earned the most ticket revenue in October 2026?")
    else:
        getattr(stages, cmd)()
    audit("stage_done", stage=cmd)

if __name__ == "__main__":
    main()
