"""Print part of a file with line numbers and syntax colours (our own helper for the video).
Usage: python3 scripts/show.py <file> [first_line] [last_line]"""
import sys
from rich.console import Console
from rich.syntax import Syntax
path = sys.argv[1]; a = int(sys.argv[2]) if len(sys.argv) > 2 else 1
lines = open(path).read().splitlines(); b = int(sys.argv[3]) if len(sys.argv) > 3 else len(lines)
lexer = {"xml": "xml", "json": "json", "py": "python", "sql": "sql", "sh": "bash", "csv": "text"}.get(path.rsplit(".", 1)[-1], "text")
Console(force_terminal=True).print(Syntax("\n".join(lines), lexer, theme="monokai", background_color="default",
                                          line_numbers=True, line_range=(a, b)))
