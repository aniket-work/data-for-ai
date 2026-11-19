"""Print lines of a file with syntax colors:  python show.py FILE [FIRST LAST]   (our own small helper)"""
import sys, pathlib
from rich.console import Console
from rich.syntax import Syntax
p = pathlib.Path(sys.argv[1]); lines = p.read_text().splitlines()
a, b = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1, len(lines))
lang = {".ttl": "turtle", ".rq": "sparql", ".yaml": "yaml", ".py": "python"}.get(p.suffix, "text")
Console(highlight=False).print(Syntax("\n".join(lines[a - 1:b]), lang, theme="monokai", background_color="default"))
