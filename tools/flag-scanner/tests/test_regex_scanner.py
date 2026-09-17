from pathlib import Path
from flag_scanner.scanner.regex_scanner import scan_file_with_regex

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample-project"

def test_regex_finds_ts_calls():
    service_ts = FIXTURES_DIR / "service.ts"
    occurrences = scan_file_with_regex(service_ts)
    
    flag_keys = {occ.flag_key for occ in occurrences}
    assert "checkout-v2" in flag_keys
    assert "dark-mode" in flag_keys
    assert "payment-v2" in flag_keys

def test_regex_ignores_comments():
    service_ts = FIXTURES_DIR / "service.ts"
    occurrences = scan_file_with_regex(service_ts)
    
    flag_keys = {occ.flag_key for occ in occurrences}
    assert "commented-flag-key" not in flag_keys
    assert "multi-line-commented-flag" not in flag_keys

def test_regex_ignores_plain_strings():
    service_ts = FIXTURES_DIR / "service.ts"
    occurrences = scan_file_with_regex(service_ts)
    # Ensure plain string "decoy" wasn't matched as a new flag
    flag_keys = {occ.flag_key for occ in occurrences}
    assert "decoy" not in flag_keys
