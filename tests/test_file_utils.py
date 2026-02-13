"""Tests for core/file_utils.py — read_file_safe, list_files"""

import pytest
from pathlib import Path
from ai_code.core.file_utils import read_file_safe, list_files


class TestReadFileSafe:
    def test_read_existing_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        result = read_file_safe(str(f))
        assert result == "hello world"

    def test_read_utf8_content(self, tmp_path):
        f = tmp_path / "korean.txt"
        f.write_text("안녕하세요", encoding="utf-8")
        result = read_file_safe(str(f))
        assert result == "안녕하세요"

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_file_safe(str(tmp_path / "nope.txt"))

    def test_directory_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_file_safe(str(tmp_path))


class TestListFiles:
    def test_single_file(self, tmp_path):
        f = tmp_path / "one.py"
        f.write_text("pass")
        result = list_files(str(f))
        assert len(result) == 1
        assert result[0] == f.resolve()

    def test_directory_lists_all_files(self, tmp_path):
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.py").write_text("b")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.py").write_text("c")
        result = list_files(str(tmp_path))
        assert len(result) == 3

    def test_directory_excludes_node_modules(self, tmp_path):
        (tmp_path / "ok.py").write_text("ok")
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "bad.js").write_text("bad")
        result = list_files(str(tmp_path))
        names = [p.name for p in result]
        assert "ok.py" in names
        assert "bad.js" not in names

    def test_directory_excludes_dist(self, tmp_path):
        (tmp_path / "ok.py").write_text("ok")
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "bundle.js").write_text("x")
        result = list_files(str(tmp_path))
        names = [p.name for p in result]
        assert "bundle.js" not in names

    def test_nonexistent_path_raises(self):
        with pytest.raises((FileNotFoundError, NotImplementedError)):
            list_files("/absolutely/no/way/this/exists_xyz_12345")

    def test_nonexistent_relative_path_raises(self):
        with pytest.raises(FileNotFoundError):
            list_files("no_such_dir_xyz_12345/no_file.py")

    def test_glob_pattern(self, tmp_path, monkeypatch):
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        monkeypatch.chdir(tmp_path)
        result = list_files("*.py")
        assert len(result) == 1
        assert result[0].name == "a.py"
