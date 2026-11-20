"""Ask the bank a question, raw or through WrenAI, or run the whole eval.

  python ask.py raw  "What is the delinquency rate for small-business loans?"
  python ask.py wren "What is the delinquency rate for small-business loans?"
  python ask.py raw+ "..."                   # DDL plus sample rows and column values
  python ask.py eval [raw|raw+|wren|all]    # every question in eval/questions.yml -> eval/runs/<arm>.json
"""
import json, sys, yaml
from t2s import config
from t2s.trace import ask, console

def main():
    if len(sys.argv) >= 3 and sys.argv[1] in ("raw", "raw+", "wren"):
        ask(sys.argv[1], " ".join(sys.argv[2:]))
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "eval":
        which = sys.argv[2] if len(sys.argv) > 2 else "all"
        qs = yaml.safe_load(open(config.EVAL / "questions.yml"))
        (config.EVAL / "runs").mkdir(exist_ok=True)
        for arm in (["raw", "raw+", "wren"] if which == "all" else [which]):
            path = config.EVAL / "runs" / f"{arm}.json"
            runs = json.load(open(path)) if path.exists() else {}
            for q in qs:
                if q["id"] in runs:
                    continue   # resumable
                console.print(f"[bold]{arm} {q['id']}[/] {q['question']}")
                runs[q["id"]] = ask(arm, q["question"], quiet=True)
                console.print(f"   {runs[q['id']]['seconds']} s, steps: {', '.join(runs[q['id']]['steps']) or '-'}")
                json.dump(runs, open(path, "w"), indent=2)
        return
    print(__doc__)

if __name__ == "__main__":
    main()
