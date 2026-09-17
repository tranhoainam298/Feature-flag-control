"""Reconciliation logic comparing source code flag occurrences with server status."""

from collections import defaultdict
from flag_scanner.models import Occurrence, ServerFlag, FlagReport, FlagStatus, ScanSummary


def reconcile_flags(
    occurrences: list[Occurrence],
    server_flags: dict[str, ServerFlag] | None,
) -> list[FlagReport]:
    """Reconcile detected code occurrences against server flags.

    Classifies each flag into:
    - DEAD: ARCHIVED on server, but still referenced in code.
    - STALE: High debt score (>= 60) or STALE state on server, in code.
    - UNDECLARED: In code, but not found on server.
    - ORPHAN: On server, but not referenced in code.
    - OK: Normal active flag referenced in code.
    - UNKNOWN: In code, but server not connected (offline mode).
    """
    # Group occurrences by flag_key
    code_map: dict[str, list[Occurrence]] = defaultdict(list)
    for occ in occurrences:
        code_map[occ.flag_key].append(occ)

    reports: list[FlagReport] = []

    # If server_flags is None (offline mode), report all code flags as UNKNOWN
    if server_flags is None:
        for flag_key, occs in code_map.items():
            reports.append(
                FlagReport(
                    flag_key=flag_key,
                    status=FlagStatus.UNKNOWN,
                    debt_score=0,
                    occurrences=occs,
                    recommendation="Chạy ở chế độ offline, chưa đối chiếu với máy chủ",
                )
            )
        return reports

    # Process flags present in code
    for flag_key, occs in code_map.items():
        if flag_key in server_flags:
            s_flag = server_flags[flag_key]
            debt = s_flag.debt_score

            if s_flag.state == "ARCHIVED":
                status = FlagStatus.DEAD
                rec = "Xóa nhánh điều kiện và bỏ lời gọi SDK khỏi mã nguồn (flag đã bị ARCHIVED)"
            elif s_flag.state == "STALE" or debt >= 60:
                status = FlagStatus.STALE
                rec = "Dọn dẹp code hoặc hoàn tất rollout để giảm nợ kỹ thuật (flag có debt score cao)"
            else:
                status = FlagStatus.OK
                rec = "Cờ tính năng đang hoạt động bình thường"

            reports.append(
                FlagReport(
                    flag_key=flag_key,
                    status=status,
                    debt_score=debt,
                    occurrences=occs,
                    recommendation=rec,
                )
            )
        else:
            # Found in code, not on server
            reports.append(
                FlagReport(
                    flag_key=flag_key,
                    status=FlagStatus.UNDECLARED,
                    debt_score=0,
                    occurrences=occs,
                    recommendation="Flag chưa được khai báo trên server hoặc có thể gõ sai tên key",
                )
            )

    # Process ORPHAN flags (present on server, but not in code)
    for s_key, s_flag in server_flags.items():
        if s_key not in code_map:
            # We skip reporting ARCHIVED flags that are already not in code (they are truly retired)
            if s_flag.state != "ARCHIVED":
                reports.append(
                    FlagReport(
                        flag_key=s_key,
                        status=FlagStatus.ORPHAN,
                        debt_score=s_flag.debt_score,
                        occurrences=[],
                        recommendation="Flag có trên server nhưng không tìm thấy trong code, có thể cân nhắc archive",
                    )
                )

    # Sort reports: DEAD first, then STALE, UNDECLARED, ORPHAN, OK
    order = {
        FlagStatus.DEAD: 0,
        FlagStatus.STALE: 1,
        FlagStatus.UNDECLARED: 2,
        FlagStatus.ORPHAN: 3,
        FlagStatus.UNKNOWN: 4,
        FlagStatus.OK: 5,
    }
    reports.sort(key=lambda r: (order.get(r.status, 9), -r.debt_score, r.flag_key))
    return reports


def calculate_summary(reports: list[FlagReport]) -> ScanSummary:
    """Compute aggregate summary counts from reports."""
    summary = ScanSummary()
    for r in reports:
        if r.status == FlagStatus.DEAD:
            summary.dead += 1
            summary.total_code_flags += 1
        elif r.status == FlagStatus.STALE:
            summary.stale += 1
            summary.total_code_flags += 1
        elif r.status == FlagStatus.UNDECLARED:
            summary.undeclared += 1
            summary.total_code_flags += 1
        elif r.status == FlagStatus.ORPHAN:
            summary.orphan += 1
        elif r.status == FlagStatus.OK:
            summary.ok += 1
            summary.total_code_flags += 1
        elif r.status == FlagStatus.UNKNOWN:
            summary.unknown += 1
            summary.total_code_flags += 1

    return summary
