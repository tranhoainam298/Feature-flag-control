from pathlib import Path
from flag_scanner.scanner.ast_parser import parse_python_file

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample-project"

def test_ast_finds_nested_calls():
    app_py = FIXTURES_DIR / "app.py"
    occurrences = parse_python_file(app_py)
    
    flag_keys = {occ.flag_key for occ in occurrences}
    assert "checkout-v2" in flag_keys
    assert "new-homepage" in flag_keys
    assert "payment-v2" in flag_keys
    assert "dead-feature-flag" in flag_keys

def test_ast_ignores_comments_and_plain_strings():
    app_py = FIXTURES_DIR / "app.py"
    occurrences = parse_python_file(app_py)
    
    flag_keys = {occ.flag_key for occ in occurrences}
    assert "decoy-in-comment-1" not in flag_keys
    assert "non-existent-flag-in-string-only" not in flag_keys

def test_ast_captures_correct_line_numbers_and_snippets():
    app_py = FIXTURES_DIR / "app.py"
    occurrences = parse_python_file(app_py)
    
    occ_map = {occ.flag_key: occ for occ in occurrences}
    occ_checkout = occ_map["checkout-v2"]
    assert occ_checkout.line_number > 0
    assert "is_enabled" in occ_checkout.code_snippet
    assert "checkout-v2" in occ_checkout.code_snippet

def test_ast_gracefully_handles_syntax_errors():
    broken_py = FIXTURES_DIR / "invalid_syntax.py"
    # Should return empty list and NOT raise SyntaxError
    occurrences = parse_python_file(broken_py)
    assert occurrences == []
