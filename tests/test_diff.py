"""Tests for core/diff.py — make_unified_diff"""

from pathlib import Path
from ai_code.core.diff import make_unified_diff


class TestMakeUnifiedDiff:
    def test_identical_code_produces_empty_diff(self):
        code = "def foo():\n    return 1\n"
        result = make_unified_diff(code, code, Path("test.py"))
        assert result == ""

    def test_changed_code_produces_diff(self):
        original = "def foo():\n    return 1\n"
        new = "def foo():\n    return 2\n"
        result = make_unified_diff(original, new, Path("test.py"))
        assert "---" in result
        assert "+++" in result
        assert "-    return 1" in result
        assert "+    return 2" in result

    def test_diff_contains_file_path(self):
        original = "a\n"
        new = "b\n"
        path = Path("src/main.py")
        result = make_unified_diff(original, new, path)
        assert "src/main.py" in result

    def test_added_lines(self):
        original = "line1\n"
        new = "line1\nline2\n"
        result = make_unified_diff(original, new, Path("f.txt"))
        assert "+line2" in result

    def test_removed_lines(self):
        original = "line1\nline2\n"
        new = "line1\n"
        result = make_unified_diff(original, new, Path("f.txt"))
        assert "-line2" in result

    def test_empty_to_content(self):
        result = make_unified_diff("", "hello\n", Path("new.txt"))
        assert "+hello" in result

    def test_content_to_empty(self):
        result = make_unified_diff("hello\n", "", Path("del.txt"))
        assert "-hello" in result
