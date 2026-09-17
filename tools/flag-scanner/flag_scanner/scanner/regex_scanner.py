"""Constrained regex scanner for non-Python source files (JS, TS, Java, Go, etc.)."""

import re
from pathlib import Path
from flag_scanner.models import Occurrence

# Matches method calls like client.isEnabled("checkout-v2") or client.getBooleanValue('key', false)
CALL_PATTERN = re.compile(
    r"\.\s*(?:is_?enabled|get_?boolean(?:_?value)?|get_?string(?:_?value)?|get_?number(?:_?value)?|get_?json(?:_?value)?|get_?variant|get_?evaluation)\s*\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)


def _strip_comments_preserving_lines(text: str) -> list[str]:
    """Strip single-line and multi-line comments while keeping line count intact."""
    lines = text.splitlines()
    cleaned_lines = []
    in_block_comment = False

    for line in lines:
        cleaned = line
        if in_block_comment:
            if "*/" in cleaned:
                # End of block comment
                _, post = cleaned.split("*/", 1)
                cleaned = " " + post
                in_block_comment = False
            else:
                cleaned = ""

        if not in_block_comment:
            # Handle start of block comment on this line
            while "/*" in cleaned:
                pre, remainder = cleaned.split("/*", 1)
                if "*/" in remainder:
                    _, post = remainder.split("*/", 1)
                    cleaned = pre + " " + post
                else:
                    cleaned = pre
                    in_block_comment = True
                    break

            # Strip single line comment //
            if "//" in cleaned:
                cleaned = cleaned.split("//", 1)[0]
            # Strip bash/yaml/python style single line comment # if not string
            if "#" in cleaned and not any(q in cleaned for q in ("'", '"')):
                cleaned = cleaned.split("#", 1)[0]

        cleaned_lines.append(cleaned)

    return cleaned_lines


def scan_file_with_regex(file_path: Path | str) -> list[Occurrence]:
    """Scan a non-Python file with constrained regex and return detected flag occurrences."""
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return []

    original_lines = content.splitlines()
    cleaned_lines = _strip_comments_preserving_lines(content)

    occurrences: list[Occurrence] = []

    for idx, (clean_line, orig_line) in enumerate(zip(cleaned_lines, original_lines), start=1):
        for match in CALL_PATTERN.finditer(clean_line):
            flag_key = match.group(1).strip()
            if flag_key:
                occurrences.append(
                    Occurrence(
                        flag_key=flag_key,
                        file_path=str(path),
                        line_number=idx,
                        code_snippet=orig_line.strip(),
                    )
                )

    return occurrences
