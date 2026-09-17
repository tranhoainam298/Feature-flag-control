"""Command-line interface entry point for flag-scanner."""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from flag_scanner.config import load_config, init_config
from flag_scanner.models import Occurrence, FlagStatus
from flag_scanner.reconciler import reconcile_flags, calculate_summary
from flag_scanner.reporter import format_text, format_json, format_markdown
from flag_scanner.scanner.ast_parser import parse_python_file
from flag_scanner.scanner.regex_scanner import scan_file_with_regex
from flag_scanner.scanner.walker import walk_directory
from flag_scanner.server import fetch_server_flags


def run_scan_command(
    path: str,
    api_url: str = "",
    api_key: str = "",
    format_type: str = "text",
    fail_on_dead: bool = False,
    output_file: str | None = None,
) -> int:
    """Execute code scan, reconcile with server, and format output.

    Returns exit code (0 for success, 1 if fail_on_dead is triggered).
    """
    target = Path(path).resolve()
    if not target.exists():
        print(f"Error: Path '{path}' does not exist.", file=sys.stderr)
        return 2

    # Discover files
    files = walk_directory(target)

    # Scan each file
    all_occurrences: list[Occurrence] = []
    for file_path in files:
        if file_path.suffix == ".py":
            occs = parse_python_file(file_path)
        else:
            occs = scan_file_with_regex(file_path)
        all_occurrences.extend(occs)

    # Fetch server flags if credentials provided
    server_flags = fetch_server_flags(api_url, api_key) if (api_url and api_key) else None

    # Reconcile
    reports = reconcile_flags(all_occurrences, server_flags)

    # Format output
    fmt = format_type.lower()
    if fmt == "json":
        output_str = format_json(reports)
    elif fmt in ("markdown", "md"):
        output_str = format_markdown(reports)
    else:
        output_str = format_text(reports)

    # Output to stdout or file
    if output_file:
        Path(output_file).write_text(output_str, encoding="utf-8")
        print(f"Report written to {output_file}")
    else:
        # Avoid windows encoding errors when stdout is redirected
        try:
            print(output_str)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(output_str.encode("utf-8") + b"\n")

    summary = calculate_summary(reports)

    # Check CI quality gate
    if fail_on_dead and summary.dead > 0:
        return 1

    return 0


def run_init_command(output_path: str = ".flagscanner.toml") -> int:
    """Initialize default .flagscanner.toml configuration file."""
    dest = init_config(output_path)
    print(f"Created configuration file at {dest}")
    return 0


def main(argv: list[str] | None = None) -> None:
    """Main CLI entrypoint."""
    args_list = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="flag-scanner",
        description="FlagOps Feature Flag Codebase Scanner & Quality Gate CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan subcommand
    scan_parser = subparsers.add_parser("scan", help="Scan codebase for flag usages")
    scan_parser.add_argument("path", nargs="?", default=".", help="Directory or file path to scan")
    scan_parser.add_argument("--api-url", default=None, help="FlagOps API URL (e.g. http://localhost:8000)")
    scan_parser.add_argument("--api-key", default=None, help="FlagOps Server SDK API Key")
    scan_parser.add_argument("--format", choices=["text", "json", "markdown"], default=None, help="Output format")
    scan_parser.add_argument("--fail-on-dead", action="store_true", default=None, help="Exit with code 1 if dead flags exist")
    scan_parser.add_argument("--output", "-o", default=None, help="Write output to file instead of stdout")

    # report subcommand
    report_parser = subparsers.add_parser("report", help="Generate a comprehensive markdown report")
    report_parser.add_argument("path", nargs="?", default=".", help="Directory or file path to scan")
    report_parser.add_argument("--output", "-o", default="report.md", help="Output report file (default: report.md)")
    report_parser.add_argument("--api-url", default=None, help="FlagOps API URL")
    report_parser.add_argument("--api-key", default=None, help="FlagOps Server SDK API Key")

    # init subcommand
    init_parser = subparsers.add_parser("init", help="Create a default .flagscanner.toml configuration file")
    init_parser.add_argument("--output", "-o", default=".flagscanner.toml", help="Destination file path")

    parsed = parser.parse_args(args_list)

    # Load configuration file defaults if present
    cfg = load_config()
    scanner_cfg = cfg.get("scanner", {})
    server_cfg = cfg.get("server", {})

    if parsed.command == "init":
        sys.exit(run_init_command(parsed.output))

    if parsed.command == "report":
        api_url = parsed.api_url or server_cfg.get("api_url") or os.getenv("FLAGOPS_API_URL", "")
        api_key = parsed.api_key or server_cfg.get("api_key") or os.getenv("FLAGOPS_API_KEY", "")
        exit_code = run_scan_command(
            path=parsed.path,
            api_url=api_url,
            api_key=api_key,
            format_type="markdown",
            fail_on_dead=False,
            output_file=parsed.output,
        )
        sys.exit(exit_code)

    # Default to scan if no subcommand or 'scan'
    if parsed.command == "scan" or parsed.command is None:
        target_path = getattr(parsed, "path", ".") if parsed.command == "scan" else (args_list[0] if args_list and not args_list[0].startswith("-") else ".")
        api_url = (getattr(parsed, "api_url", None) or server_cfg.get("api_url") or os.getenv("FLAGOPS_API_URL", "http://localhost:8000"))
        api_key = (getattr(parsed, "api_key", None) or server_cfg.get("api_key") or os.getenv("FLAGOPS_API_KEY", ""))
        format_type = getattr(parsed, "format", None) or scanner_cfg.get("format", "text")
        fail_on_dead = getattr(parsed, "fail_on_dead", None)
        if fail_on_dead is None:
            fail_on_dead = scanner_cfg.get("fail_on_dead", False)
        output_file = getattr(parsed, "output", None)

        exit_code = run_scan_command(
            path=target_path,
            api_url=api_url,
            api_key=api_key,
            format_type=format_type,
            fail_on_dead=bool(fail_on_dead),
            output_file=output_file,
        )
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
