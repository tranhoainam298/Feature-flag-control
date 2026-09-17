from flag_scanner.models import Occurrence, ServerFlag, FlagStatus
from flag_scanner.reconciler import reconcile_flags

def test_reconcile_dead_flag():
    occurrences = [
        Occurrence(flag_key="old-flag", file_path="app.py", line_number=10, code_snippet="client.is_enabled('old-flag')")
    ]
    server_flags = {
        "old-flag": ServerFlag(key="old-flag", state="ARCHIVED", debt_score=80, is_temporary=True)
    }
    
    reports = reconcile_flags(occurrences, server_flags)
    assert len(reports) == 1
    assert reports[0].status == FlagStatus.DEAD
    assert "Xóa" in reports[0].recommendation

def test_reconcile_stale_flag():
    occurrences = [
        Occurrence(flag_key="stale-flag", file_path="app.py", line_number=12, code_snippet="client.is_enabled('stale-flag')")
    ]
    server_flags = {
        "stale-flag": ServerFlag(key="stale-flag", state="STALE", debt_score=75, is_temporary=False)
    }
    
    reports = reconcile_flags(occurrences, server_flags)
    assert len(reports) == 1
    assert reports[0].status == FlagStatus.STALE

def test_reconcile_undeclared_flag():
    occurrences = [
        Occurrence(flag_key="typo-flag", file_path="app.py", line_number=15, code_snippet="client.is_enabled('typo-flag')")
    ]
    server_flags = {}  # Not on server
    
    reports = reconcile_flags(occurrences, server_flags)
    assert len(reports) == 1
    assert reports[0].status == FlagStatus.UNDECLARED

def test_reconcile_orphan_flag():
    occurrences = []  # No occurrences in code
    server_flags = {
        "unused-flag": ServerFlag(key="unused-flag", state="ACTIVE", debt_score=10, is_temporary=False)
    }
    
    reports = reconcile_flags(occurrences, server_flags)
    assert len(reports) == 1
    assert reports[0].status == FlagStatus.ORPHAN

def test_reconcile_ok_flag():
    occurrences = [
        Occurrence(flag_key="active-flag", file_path="app.py", line_number=20, code_snippet="client.is_enabled('active-flag')")
    ]
    server_flags = {
        "active-flag": ServerFlag(key="active-flag", state="ACTIVE", debt_score=15, is_temporary=False)
    }
    
    reports = reconcile_flags(occurrences, server_flags)
    assert len(reports) == 1
    assert reports[0].status == FlagStatus.OK
