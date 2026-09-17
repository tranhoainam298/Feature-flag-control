"""Directory traversal and file discovery with ignore filtering."""

import os
from pathlib import Path

DEFAULT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".json", ".yaml", ".yml"
}

DEFAULT_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    "dist", "build", ".pytest_cache", ".hypothesis", ".ruff_cache",
    ".idea", ".vscode", "coverage", ".mypy_cache"
}


def _load_gitignore_patterns(root_dir: Path) -> set[str]:
    """Extract simple ignore patterns from .gitignore in root_dir."""
    gitignore = root_dir / ".gitignore"
    patterns = set()
    if gitignore.is_file():
        try:
            for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    # Strip leading / or trailing /
                    patterns.add(stripped.strip("/"))
        except Exception:
            pass
    return patterns


def walk_directory(
    target_path: str | Path,
    extensions: set[str] | None = None,
    custom_ignores: set[str] | None = None,
) -> list[Path]:
    """Recursively collect matching source code files in target_path."""
    path = Path(target_path).resolve()
    valid_exts = extensions or DEFAULT_EXTENSIONS
    ignore_set = set(DEFAULT_IGNORE_DIRS)
    if custom_ignores:
        ignore_set.update(custom_ignores)

    # If target_path is a single file, check its extension directly
    if path.is_file():
        return [path] if path.suffix in valid_exts else []

    if not path.is_dir():
        return []

    # Read gitignore if available
    ignore_set.update(_load_gitignore_patterns(path))

    matched_files: list[Path] = []

    for root, dirs, files in os.walk(path):
        # Prune ignored directories in-place
        dirs[:] = [
            d for d in dirs
            if d not in ignore_set and not any(p in d for p in ignore_set)
        ]

        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix in valid_exts:
                matched_files.append(file_path)

    return sorted(matched_files)
