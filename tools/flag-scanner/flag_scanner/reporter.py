"""Formatting reporters for text, JSON, and markdown outputs."""

import json
from dataclasses import asdict
from flag_scanner.models import FlagReport, FlagStatus
from flag_scanner.reconciler import calculate_summary


def format_text(reports: list[FlagReport]) -> str:
    """Format reports in human-readable plain text."""
    lines: list[str] = []
    summary = calculate_summary(reports)

    for r in reports:
        lines.append(f"Flag: {r.flag_key}")
        status_line = f"Status: {r.status.value}"
        if r.debt_score > 0:
            status_line += f"  |  Debt: {r.debt_score}/100"
        lines.append(status_line)

        lines.append(f"Occurrences: {len(r.occurrences)}")
        if r.occurrences:
            lines.append("Files:")
            for occ in r.occurrences:
                lines.append(f"    {occ.file_path}:{occ.line_number}")
        if r.recommendation:
            lines.append(f"Recommendation: {r.recommendation}")
        lines.append("")

    # Summary line
    if summary.unknown > 0:
        summary_str = (
            f"Tổng kết: {summary.total_code_flags} flag trong code (Chế độ offline, chưa đối chiếu server)"
        )
    else:
        summary_str = (
            f"Tổng kết: {summary.total_code_flags} flag trong code, "
            f"{summary.dead} DEAD, {summary.stale} STALE, "
            f"{summary.undeclared} UNDECLARED, {summary.orphan} ORPHAN, {summary.ok} OK"
        )
    lines.append(summary_str)
    return "\n".join(lines)


def format_json(reports: list[FlagReport], indent: int = 2) -> str:
    """Format reports and summary as valid JSON."""
    summary = calculate_summary(reports)
    payload = {
        "summary": asdict(summary),
        "reports": [
            {
                "flag_key": r.flag_key,
                "status": r.status.value,
                "debt_score": r.debt_score,
                "occurrences_count": len(r.occurrences),
                "occurrences": [asdict(occ) for occ in r.occurrences],
                "recommendation": r.recommendation,
            }
            for r in reports
        ],
    }
    return json.dumps(payload, indent=indent, ensure_ascii=False)


def format_markdown(reports: list[FlagReport]) -> str:
    """Format reports as a comprehensive GitHub-flavored Markdown document."""
    summary = calculate_summary(reports)
    lines: list[str] = [
        "# FlagOps Flag Scanner Report",
        "",
        "## Tổng quan",
        "",
        f"- **Tổng số flag trong code:** {summary.total_code_flags}",
        f"- **DEAD (Cờ đã archived nhưng còn trong code):** {summary.dead}",
        f"- **STALE (Cờ có điểm nợ cao, cần dọn dẹp):** {summary.stale}",
        f"- **UNDECLARED (Cờ chưa khai báo trên server):** {summary.undeclared}",
        f"- **ORPHAN (Cờ trên server nhưng không có trong code):** {summary.orphan}",
        f"- **OK (Cờ hoạt động bình thường):** {summary.ok}",
        "",
        "## Chi tiết cờ tính năng",
        "",
        "| Flag Key | Trạng thái | Điểm nợ | Số lần xuất hiện | Khuyến nghị hành động |",
        "|---|---|---|---|---|",
    ]

    for r in reports:
        debt_display = f"{r.debt_score}/100" if r.debt_score > 0 else "—"
        lines.append(
            f"| `{r.flag_key}` | **{r.status.value}** | {debt_display} | {len(r.occurrences)} | {r.recommendation} |"
        )

    lines.append("")
    lines.append("## Danh sách vị trí trong mã nguồn")
    lines.append("")

    for r in reports:
        if r.occurrences:
            lines.append(f"### `{r.flag_key}` ({r.status.value})")
            for occ in r.occurrences:
                lines.append(f"- `{occ.file_path}:{occ.line_number}`")
                if occ.code_snippet:
                    lines.append(f"  ```\n  {occ.code_snippet}\n  ```")
            lines.append("")

    return "\n".join(lines)
