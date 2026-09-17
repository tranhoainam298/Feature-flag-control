"""Parity tests verifying sdk/python/flagops/engine is 100% identical to backend/app/engine."""

from pathlib import Path


def test_engine_source_code_identical_parity():
    """Verify every engine file in backend and sdk has identical content."""
    # Find backend and sdk engine dirs
    this_file = Path(__file__).resolve()
    # sdk/python/tests/test_engine_parity.py -> sdk/python/flagops/engine
    sdk_engine_dir = this_file.parent.parent / "flagops" / "engine"
    # repo root / backend / app / engine
    repo_root = this_file.parent.parent.parent.parent
    backend_engine_dir = repo_root / "backend" / "app" / "engine"

    assert sdk_engine_dir.exists(), f"SDK engine dir not found at {sdk_engine_dir}"
    assert backend_engine_dir.exists(), f"Backend engine dir not found at {backend_engine_dir}"

    expected_files = [
        "__init__.py",
        "types.py",
        "operators.py",
        "bucketing.py",
        "matcher.py",
        "evaluator.py",
    ]

    for fname in expected_files:
        sdk_file = sdk_engine_dir / fname
        backend_file = backend_engine_dir / fname

        assert sdk_file.exists(), f"Missing SDK file: {fname}"
        assert backend_file.exists(), f"Missing backend file: {fname}"

        sdk_content = sdk_file.read_text(encoding="utf-8").replace("\r\n", "\n")
        backend_content = backend_file.read_text(encoding="utf-8").replace("\r\n", "\n")

        assert (
            sdk_content == backend_content
        ), f"Drift detected in engine file '{fname}' between backend and SDK!"
