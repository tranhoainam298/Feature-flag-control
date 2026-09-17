from pathlib import Path
from flag_scanner.cli import run_scan_command, run_init_command

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample-project"

def test_cli_scan_offline(capsys):
    # Running without server should not crash, returns 0 exit code
    exit_code = run_scan_command(
        path=str(FIXTURES_DIR),
        api_url="",
        api_key="",
        format_type="text",
        fail_on_dead=False,
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "checkout-v2" in captured.out

def test_cli_scan_json_format(capsys):
    exit_code = run_scan_command(
        path=str(FIXTURES_DIR),
        api_url="",
        api_key="",
        format_type="json",
        fail_on_dead=False,
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    import json
    data = json.loads(captured.out)
    assert "reports" in data

def test_cli_init_command(tmp_path):
    config_file = tmp_path / ".flagscanner.toml"
    run_init_command(output_path=str(config_file))
    assert config_file.exists()
    content = config_file.read_text(encoding="utf-8")
    assert "[scanner]" in content
    assert "[server]" in content

def test_cli_fail_on_dead_exit_code_1(monkeypatch):
    from flag_scanner.models import ServerFlag
    def mock_fetch(*args, **kwargs):
        return {
            "checkout-v2": ServerFlag(key="checkout-v2", state="ARCHIVED", debt_score=95)
        }
    monkeypatch.setattr("flag_scanner.cli.fetch_server_flags", mock_fetch)
    exit_code = run_scan_command(
        path=str(FIXTURES_DIR),
        api_url="http://test",
        api_key="test_key",
        format_type="text",
        fail_on_dead=True,
    )
    assert exit_code == 1

