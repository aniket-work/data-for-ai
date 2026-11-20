"""Pretty-print a file (or a line range) with syntax colours: python scripts/show.py FILE [START-END]"""
import sys
from rich.console import Console
from rich.syntax import Syntax
path = sys.argv[1]; a, b = (map(int, sys.argv[2].split("-")) if len(sys.argv) > 2 else (1, None))
code = open(path).read()
lexer = "yaml" if path.endswith((".yml", ".yaml")) else "sql" if path.endswith(".sql") else "markdown" if path.endswith(".md") else "text"
Console(width=146, force_terminal=True, color_system="truecolor").print(Syntax(code, lexer, theme="monokai", line_numbers=True, line_range=(a, b),
                                background_color="#020617", word_wrap=path.endswith(".md")))
