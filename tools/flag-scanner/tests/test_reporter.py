import json
from flag_scanner.models import Occurrence, FlagReport, FlagStatus
from flag_scanner.reporter import format_text, format_json, format_markdown

def _sample_reports():
    return [
        FlagReport(
            flag_key="checkout-v2",
            status=FlagStatus.DEAD,
            debt_score=87,
            occurrences=[
                Occurrence("checkout-v2", "demo-app/main.py", 31, "client.is_enabled('checkout-v2')"),
                Occurrence("checkout-v2", "demo-app/checkout.py", 90, "client.is_enabled('checkout-v2')"),
            ],
            recommendation="Xóa nhánh điều kiện và bỏ lời gọi SDK",
        )
    ]

def test_format_text_output():
    reports = _sample_reports()
    text = format_text(reports)
    
    assert "Flag: checkout-v2" in text
    assert "Status: DEAD" in text
    assert "Debt: 87/100" in text
    assert "Occurrences: 2" in text
    assert "demo-app/main.py:31" in text
    assert "Tổng kết:" in text

def test_format_json_output():
    reports = _sample_reports()
    json_str = format_json(reports)
    
    data = json.loads(json_str)
    assert "reports" in data
    assert "summary" in data
    assert data["summary"]["dead"] == 1
    assert data["reports"][0]["flag_key"] == "checkout-v2"

def test_format_markdown_output():
    reports = _sample_reports()
    md = format_markdown(reports)
    
    assert "# FlagOps Flag Scanner Report" in md
    assert "checkout-v2" in md
    assert "DEAD" in md
