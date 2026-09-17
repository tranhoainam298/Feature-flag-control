"""Python AST parser for high-precision feature flag detection."""

import ast
from pathlib import Path
from flag_scanner.models import Occurrence

SDK_FLAG_METHODS = {
    "is_enabled",
    "get_boolean",
    "get_string",
    "get_number",
    "get_json",
    "get_variant",
    "get_evaluation",
}


class FlagCallVisitor(ast.NodeVisitor):
    """AST visitor that detects calls to FlagOps SDK flag evaluation methods."""

    def __init__(self, file_path: str, lines: list[str]) -> None:
        self.file_path = file_path
        self.lines = lines
        self.occurrences: list[Occurrence] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Check if the call is an attribute method call (e.g. obj.is_enabled(...))
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in SDK_FLAG_METHODS:
                flag_key = self._extract_flag_key(node)
                if flag_key:
                    line_no = node.lineno
                    # 1-indexed line snippet
                    snippet = self.lines[line_no - 1].strip() if line_no <= len(self.lines) else ""
                    self.occurrences.append(
                        Occurrence(
                            flag_key=flag_key,
                            file_path=self.file_path,
                            line_number=line_no,
                            code_snippet=snippet,
                        )
                    )

        self.generic_visit(node)

    def _extract_flag_key(self, node: ast.Call) -> str | None:
        """Extract constant string flag key from positional or keyword args."""
        # 1. First positional argument
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            return node.args[0].value

        # 2. Check keyword argument: flag_key="..."
        for kw in node.keywords:
            if kw.arg in ("flag_key", "key") and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                return kw.value.value

        return None


def parse_python_file(file_path: Path | str) -> list[Occurrence]:
    """Parse a python file using AST and return all detected flag occurrences.

    Catches SyntaxError and file read exceptions gracefully to prevent scanner crashes.
    """
    path = Path(file_path)
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
        lines = source.splitlines()
        visitor = FlagCallVisitor(str(path), lines)
        visitor.visit(tree)
        return visitor.occurrences
    except (SyntaxError, UnicodeDecodeError, OSError):
        # File has invalid syntax or cannot be read; skip gracefully without crashing
        return []
