"""Configuration loader and initializer for .flagscanner.toml."""

import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

DEFAULT_TOML_CONTENT = """# FlagOps Flag Scanner Configuration

[scanner]
# Paths or directories to scan
paths = ["."]

# File extensions to inspect
extensions = [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".json", ".yaml", ".yml"]

# Directories to ignore
ignore_patterns = [".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"]

# Default output format: text | json | markdown
format = "text"

# Fail CI build (exit code 1) if DEAD flags exist
fail_on_dead = false

[server]
# FlagOps Core API base URL
api_url = "http://localhost:8000"

# FlagOps Server SDK API Key (e.g. fo_srv_dev_secret_key_demo_12345678)
api_key = ""
"""


def load_config(search_path: str | Path | None = None) -> dict[str, Any]:
    """Search for and load .flagscanner.toml from search_path or current working dir."""
    target_dir = Path(search_path or ".").resolve()
    if target_dir.is_file():
        target_dir = target_dir.parent

    # Traverse upward to find .flagscanner.toml
    curr = target_dir
    while True:
        candidate = curr / ".flagscanner.toml"
        if candidate.is_file():
            try:
                with open(candidate, "rb") as f:
                    return tomllib.load(f)
            except Exception:
                pass
        parent = curr.parent
        if parent == curr:
            break
        curr = parent

    return {}


def init_config(output_path: str | Path = ".flagscanner.toml") -> Path:
    """Write default .flagscanner.toml template."""
    dest = Path(output_path)
    dest.write_text(DEFAULT_TOML_CONTENT.strip() + "\n", encoding="utf-8")
    return dest
