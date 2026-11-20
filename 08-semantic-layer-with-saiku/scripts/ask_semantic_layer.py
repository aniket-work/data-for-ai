"""Ask the Northlight semantic layer a question in business words, through Saiku's AI Query API.

This client is our own teaching helper; the endpoint (POST /rest/saiku/api/ai/query) is Saiku's.
The request names measures and levels (or their synonyms); Saiku validates them against the cube,
writes the MDX, runs it, and returns typed records.
Usage: python3 scripts/ask_semantic_layer.py queries/box_office_by_genre.json
Env:   SAIKU_URL (default http://127.0.0.1:8080), SAIKU_USER / SAIKU_PASSWORD (default: demo admin login)
"""
import json, os, sys, urllib.request, base64
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.rule import Rule

url = os.environ.get("SAIKU_URL", "http://127.0.0.1:8080") + "/rest/saiku/api/ai/query"
auth = base64.b64encode(f"{os.environ.get('SAIKU_USER', 'admin')}:{os.environ.get('SAIKU_PASSWORD', 'admin')}".encode()).decode()
body = json.load(open(sys.argv[1]))
c = Console(width=140, force_terminal=True)
c.print(Rule("[bold #34D399]Request (business terms)"))
shown = "{\n" + ",\n".join(f'  "{k}": {json.dumps(v)}' for k, v in body.items() if k != "cube") + "\n}"
c.print(Syntax(shown, "json", theme="monokai", background_color="default", word_wrap=True))
req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                             headers={"Content-Type": "application/json", "Authorization": "Basic " + auth})
try:
    res = json.load(urllib.request.urlopen(req))
except urllib.error.HTTPError as e:
    err = json.load(e)
    c.print(Rule("[bold red]Saiku says"))
    c.print({k: err.get(k) for k in ("status", "field", "message", "available") if k in err})
    sys.exit(1)
md = res["metadata"]
c.print(Rule("[bold #34D399]MDX written by Saiku"))
c.print(Syntax(md["generatedMdx"], "sql", theme="monokai", background_color="default", word_wrap=True))
c.print(Rule("[bold #34D399]Typed result"))
rows = res["data"]
cols = list(rows[0].keys()) if rows else []
t = Table(header_style="bold #34D399", border_style="#334155")
for k in cols: t.add_column(k, justify="left" if not isinstance(rows[0][k], dict) else "right")
for r in rows: t.add_row(*[v["formatted"] if isinstance(v, dict) else str(v) for v in r.values()])
c.print(t)
