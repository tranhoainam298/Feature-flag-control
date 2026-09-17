from pathlib import Path
from flag_scanner.scanner.walker import walk_directory

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample-project"

def test_walker_discovers_code_files():
    files = walk_directory(FIXTURES_DIR)
    file_names = [f.name for f in files]
    
    assert "app.py" in file_names
    assert "service.ts" in file_names
    assert "invalid_syntax.py" in file_names

def test_walker_skips_ignored_directories(tmp_path):
    # Setup test structure with ignored folders
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.py").write_text("client.is_enabled('f1')")
    
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("client.is_enabled('ignored_f')")
    
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hook.py").write_text("client.is_enabled('ignored_git')")
    
    files = walk_directory(tmp_path)
    file_names = [f.name for f in files]
    
    assert "index.py" in file_names
    assert "dep.js" not in file_names
    assert "hook.py" not in file_names
