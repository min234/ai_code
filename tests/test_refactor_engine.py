"""Tests for core/refactor_engine.py — _strip_code_fences, _merge_snippet_back, _postprocess_snippet"""

from ai_code.core.refactor_engine import _strip_code_fences, _merge_snippet_back, _postprocess_snippet


class TestStripCodeFences:
    def test_removes_python_fence(self):
        text = "```python\nprint('hello')\n```"
        result = _strip_code_fences(text)
        assert result == "print('hello')"

    def test_removes_plain_fence(self):
        text = "```\nsome code\n```"
        result = _strip_code_fences(text)
        assert result == "some code"

    def test_no_fence_returns_original(self):
        text = "print('hello')"
        result = _strip_code_fences(text)
        assert result == text

    def test_only_opening_fence_returns_original(self):
        text = "```python\nprint('hello')"
        result = _strip_code_fences(text)
        assert result == text

    def test_multiline_content(self):
        text = "```js\nconst a = 1;\nconst b = 2;\nconsole.log(a + b);\n```"
        result = _strip_code_fences(text)
        assert "const a = 1;" in result
        assert "console.log(a + b);" in result
        assert "```" not in result

    def test_strips_surrounding_whitespace(self):
        text = "  ```python\ncode\n```  "
        result = _strip_code_fences(text)
        assert result == "code"

    def test_empty_string(self):
        assert _strip_code_fences("") == ""

    def test_single_line_fence_pair(self):
        # ``` and ``` on same line can't have content between
        text = "``````"
        result = _strip_code_fences(text)
        # starts and ends with ```, but only one line → no inner content
        assert result == text


class TestMergeSnippetBack:
    def test_basic_merge(self):
        all_lines = ["line1", "line2", "line3", "line4", "line5"]
        new_snippet = "new2\nnew3"
        result = _merge_snippet_back(all_lines, start_line=2, end_line=3, new_snippet=new_snippet)
        assert result == ["line1", "new2", "new3", "line4", "line5"]

    def test_merge_first_line(self):
        all_lines = ["old1", "line2", "line3"]
        result = _merge_snippet_back(all_lines, start_line=1, end_line=1, new_snippet="new1")
        assert result == ["new1", "line2", "line3"]

    def test_merge_last_line(self):
        all_lines = ["line1", "line2", "old3"]
        result = _merge_snippet_back(all_lines, start_line=3, end_line=3, new_snippet="new3")
        assert result == ["line1", "line2", "new3"]


class TestPostprocessSnippet:
    def test_identical_returns_as_is(self):
        code = "def foo(): pass"
        assert _postprocess_snippet(code, code) == code

    def test_different_returns_new(self):
        original = "def foo(): pass"
        new = "def foo():\n    pass"
        assert _postprocess_snippet(original, new) == new

    def test_extracts_after_original_duplicate(self):
        original = "x = 1"
        new = "x = 1\nx = 2"  # LLM repeated original then added new
        result = _postprocess_snippet(original, new)
        assert result == "x = 2"
