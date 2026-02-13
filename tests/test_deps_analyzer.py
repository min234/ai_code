"""Tests for core/deps_analyzer.py — collect_text_files"""

from pathlib import Path
from ai_code.core.deps_analyzer import collect_text_files


class TestCollectTextFiles:
    def test_collects_text_files(self, tmp_path):
        (tmp_path / "a.py").write_text("print('a')", encoding="utf-8")
        (tmp_path / "b.txt").write_text("hello", encoding="utf-8")
        result = collect_text_files(tmp_path)
        assert len(result) == 2
        assert any("a.py" in k for k in result)
        assert any("b.txt" in k for k in result)

    def test_skips_git_directory(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config", encoding="utf-8")
        (tmp_path / "main.py").write_text("pass", encoding="utf-8")
        result = collect_text_files(tmp_path)
        assert len(result) == 1
        assert all(".git" not in k for k in result)

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "pkg.js").write_text("module", encoding="utf-8")
        (tmp_path / "app.js").write_text("app", encoding="utf-8")
        result = collect_text_files(tmp_path)
        assert len(result) == 1
        assert "app.js" in list(result.keys())[0]

    def test_skips_venv(self, tmp_path):
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "pip.py").write_text("pip", encoding="utf-8")
        (tmp_path / "main.py").write_text("pass", encoding="utf-8")
        result = collect_text_files(tmp_path)
        assert all(".venv" not in k for k in result)

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-311.pyc").write_text("bytecode", encoding="utf-8")
        (tmp_path / "mod.py").write_text("pass", encoding="utf-8")
        result = collect_text_files(tmp_path)
        assert all("__pycache__" not in k for k in result)

    def test_respects_max_files(self, tmp_path):
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_text(f"content {i}", encoding="utf-8")
        result = collect_text_files(tmp_path, max_files=3)
        assert len(result) <= 3

    def test_skips_large_files(self, tmp_path):
        small = tmp_path / "small.txt"
        small.write_text("small", encoding="utf-8")
        big = tmp_path / "big.txt"
        big.write_text("x" * 1000, encoding="utf-8")
        result = collect_text_files(tmp_path, max_bytes=500)
        assert "small.txt" in list(result.keys())[0]
        assert all("big.txt" not in k for k in result)

    def test_empty_directory(self, tmp_path):
        result = collect_text_files(tmp_path)
        assert result == {}

    def test_returns_relative_paths(self, tmp_path):
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "main.py").write_text("pass", encoding="utf-8")
        result = collect_text_files(tmp_path)
        keys = list(result.keys())
        assert len(keys) == 1
        # path should be relative (like "src/main.py"), not absolute
        assert not keys[0].startswith("/")

    def test_file_content_is_correct(self, tmp_path):
        content = "def hello():\n    return 'world'\n"
        (tmp_path / "hello.py").write_text(content, encoding="utf-8")
        result = collect_text_files(tmp_path)
        assert list(result.values())[0] == content
