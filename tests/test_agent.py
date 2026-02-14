"""Tests for agent.py — route_user_request & run_tool_from_spec."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from ai_code.agent import route_user_request, run_tool_from_spec


# ===================================================================
# route_user_request
# ===================================================================

class TestRouteUserRequest:
    """Tests for route_user_request."""

    @patch("ai_code.agent.ask_model")
    def test_returns_valid_json_dict(self, mock_ask):
        mock_ask.return_value = {"tool": "analyze", "path": "."}
        result = route_user_request("analyze my project")
        assert result == {"tool": "analyze", "path": "."}

    @patch("ai_code.agent.ask_model")
    def test_non_dict_raises_runtime_error(self, mock_ask):
        mock_ask.return_value = "not a dict"
        with pytest.raises(RuntimeError, match="not a valid JSON object"):
            route_user_request("hello")

    @patch("ai_code.agent.ask_model")
    def test_user_prompt_contains_user_text(self, mock_ask):
        mock_ask.return_value = {"tool": "analyze", "path": "."}
        route_user_request("simplify my code")
        call_kwargs = mock_ask.call_args[1]
        assert "simplify my code" in call_kwargs["user_prompt"]


# ===================================================================
# run_tool_from_spec — analyze
# ===================================================================

class TestRunToolAnalyze:
    """Tests for the 'analyze' tool branch."""

    def test_happy_path(self, mock_list_files, mock_read_file_safe, mock_ask_model):
        mock_list_files.return_value = [Path("sample.py")]
        mock_read_file_safe.return_value = "print('hello')"
        mock_ask_model.return_value = "File looks good."

        run_tool_from_spec({"tool": "analyze", "path": ".", "summary": True})

        mock_ask_model.assert_called_once()
        assert "sample.py" in mock_ask_model.call_args[1]["user_prompt"]

    def test_file_not_found(self, mock_list_files):
        mock_list_files.side_effect = FileNotFoundError("no such dir")
        run_tool_from_spec({"tool": "analyze", "path": "/nonexistent"})
        # Should not raise — prints error via typer.echo

    def test_empty_file_list(self, mock_list_files):
        mock_list_files.return_value = []
        run_tool_from_spec({"tool": "analyze", "path": "."})

    def test_summary_flag_passed(self, mock_list_files, mock_read_file_safe, mock_ask_model):
        mock_list_files.return_value = [Path("a.py")]
        mock_read_file_safe.return_value = "x = 1"
        mock_ask_model.return_value = "ok"
        run_tool_from_spec({"tool": "analyze", "path": ".", "summary": False})
        # summary=False still runs analysis; the flag is echoed


# ===================================================================
# run_tool_from_spec — refactor_dead_code
# ===================================================================

class TestRunToolRefactorDeadCode:
    """Tests for the 'refactor_dead_code' tool branch."""

    def test_no_changes(self, mock_list_files, mock_read_file_safe):
        mock_list_files.return_value = [Path("a.py")]
        mock_read_file_safe.return_value = "x = 1"
        with patch("ai_code.agent.refactor_dead_code", return_value="x = 1"):
            run_tool_from_spec({"tool": "refactor_dead_code", "path": "."})

    def test_user_confirms_apply(self, tmp_path, mock_list_files, mock_read_file_safe):
        target = tmp_path / "a.py"
        target.write_text("import os\nx = 1\n", encoding="utf-8")
        mock_list_files.return_value = [target]
        mock_read_file_safe.return_value = "import os\nx = 1\n"

        with patch("ai_code.agent.refactor_dead_code", return_value="x = 1\n"):
            with patch("ai_code.agent.typer.confirm", return_value=True):
                run_tool_from_spec({"tool": "refactor_dead_code", "path": str(tmp_path)})

        assert target.read_text(encoding="utf-8") == "x = 1\n"

    def test_user_rejects(self, tmp_path, mock_list_files, mock_read_file_safe):
        target = tmp_path / "b.py"
        original = "import os\nx = 1\n"
        target.write_text(original, encoding="utf-8")
        mock_list_files.return_value = [target]
        mock_read_file_safe.return_value = original

        with patch("ai_code.agent.refactor_dead_code", return_value="x = 1\n"):
            with patch("ai_code.agent.typer.confirm", return_value=False):
                run_tool_from_spec({"tool": "refactor_dead_code", "path": str(tmp_path)})

        # File should remain unchanged
        assert target.read_text(encoding="utf-8") == original

    def test_file_not_found(self, mock_list_files):
        mock_list_files.side_effect = FileNotFoundError("nope")
        run_tool_from_spec({"tool": "refactor_dead_code", "path": "/bad"})

    def test_empty_file_list(self, mock_list_files):
        mock_list_files.return_value = []
        run_tool_from_spec({"tool": "refactor_dead_code", "path": "."})


# ===================================================================
# run_tool_from_spec — refactor_simplify
# ===================================================================

class TestRunToolRefactorSimplify:
    """Tests for the 'refactor_simplify' tool branch."""

    def test_happy_path(self, tmp_path, mock_list_files, mock_read_file_safe):
        target = tmp_path / "c.py"
        target.write_text("x = 1\ny = 2\n", encoding="utf-8")
        mock_list_files.return_value = [target]
        mock_read_file_safe.return_value = "x = 1\ny = 2\n"

        with patch("ai_code.agent.refactor_simplify", return_value="x, y = 1, 2\n"):
            with patch("ai_code.agent.typer.confirm", return_value=True):
                run_tool_from_spec({"tool": "refactor_simplify", "path": str(tmp_path)})

        assert target.read_text(encoding="utf-8") == "x, y = 1, 2\n"

    def test_file_not_found(self, mock_list_files):
        mock_list_files.side_effect = FileNotFoundError("nope")
        run_tool_from_spec({"tool": "refactor_simplify", "path": "/bad"})


# ===================================================================
# run_tool_from_spec — deps_analyze
# ===================================================================

class TestRunToolDepsAnalyze:
    """Tests for the 'deps_analyze' tool branch."""

    def test_no_issues(self, tmp_path):
        with patch("ai_code.agent.analyze_dependencies") as mock_analyze:
            mock_analyze.return_value = {
                "summary": "All good",
                "issues": [],
                "notes": "",
            }
            run_tool_from_spec({"tool": "deps_analyze", "path": str(tmp_path)})
            mock_analyze.assert_called_once()

    def test_user_confirms_apply(self, tmp_path):
        with patch("ai_code.agent.analyze_dependencies") as mock_analyze, \
             patch("ai_code.agent.apply_dependency_changes") as mock_apply, \
             patch("ai_code.agent.typer.confirm", return_value=True):
            mock_analyze.return_value = {
                "summary": "Issues found",
                "issues": [{"type": "unused", "file": "requirements.txt",
                            "detail": "unused pkg", "suggestion": "remove it"}],
                "notes": "",
            }
            run_tool_from_spec({"tool": "deps_analyze", "path": str(tmp_path)})
            mock_apply.assert_called_once()

    def test_user_rejects(self, tmp_path):
        with patch("ai_code.agent.analyze_dependencies") as mock_analyze, \
             patch("ai_code.agent.apply_dependency_changes") as mock_apply, \
             patch("ai_code.agent.typer.confirm", return_value=False):
            mock_analyze.return_value = {
                "summary": "Issues found",
                "issues": [{"type": "unused", "file": "req.txt",
                            "detail": "d", "suggestion": "s"}],
                "notes": "",
            }
            run_tool_from_spec({"tool": "deps_analyze", "path": str(tmp_path)})
            mock_apply.assert_not_called()

    def test_path_not_exists(self):
        run_tool_from_spec({"tool": "deps_analyze", "path": "/nonexistent_xyz_1234"})
        # Should echo error, not raise


# ===================================================================
# run_tool_from_spec — refactor_partial
# ===================================================================

class TestRunToolRefactorPartial:
    """Tests for the 'refactor_partial' tool branch."""

    def test_happy_path(self, tmp_path):
        target = tmp_path / "d.py"
        target.write_text("line1\nline2\nline3\n", encoding="utf-8")

        preview_result = {
            "results": [{
                "file_path": "d.py",
                "original_snippet": "line2",
                "refactored_snippet": "LINE2",
                "error": None,
                "applied": False,
            }]
        }
        applied_result = {
            "results": [{
                "file_path": "d.py",
                "original_snippet": "line2",
                "refactored_snippet": "LINE2",
                "error": None,
                "applied": True,
            }]
        }

        with patch("ai_code.agent.partial_refactor", side_effect=[preview_result, applied_result]):
            with patch("ai_code.agent.typer.confirm", return_value=True):
                run_tool_from_spec({
                    "tool": "refactor_partial",
                    "path": str(target),
                    "start_line": 2,
                    "end_line": 2,
                })

    def test_file_not_found(self):
        run_tool_from_spec({
            "tool": "refactor_partial",
            "path": "/nonexistent_file_xyz.py",
            "start_line": 1,
            "end_line": 1,
        })

    def test_preview_error(self, tmp_path):
        target = tmp_path / "e.py"
        target.write_text("x = 1\n", encoding="utf-8")

        preview_result = {
            "results": [{
                "file_path": "e.py",
                "error": "Model error: timeout",
                "applied": False,
            }]
        }

        with patch("ai_code.agent.partial_refactor", return_value=preview_result):
            run_tool_from_spec({
                "tool": "refactor_partial",
                "path": str(target),
                "start_line": 1,
                "end_line": 1,
            })

    def test_user_aborts(self, tmp_path):
        target = tmp_path / "f.py"
        target.write_text("a = 1\n", encoding="utf-8")

        preview_result = {
            "results": [{
                "file_path": "f.py",
                "original_snippet": "a = 1",
                "refactored_snippet": "A = 1",
                "error": None,
                "applied": False,
            }]
        }

        with patch("ai_code.agent.partial_refactor", return_value=preview_result):
            with patch("ai_code.agent.typer.confirm", return_value=False):
                run_tool_from_spec({
                    "tool": "refactor_partial",
                    "path": str(target),
                    "start_line": 1,
                    "end_line": 1,
                })


# ===================================================================
# run_tool_from_spec — convert_language
# ===================================================================

class TestRunToolConvertLanguage:
    """Tests for the 'convert_language' tool branch."""

    def test_missing_src_lang(self):
        run_tool_from_spec({
            "tool": "convert_language",
            "path": ".",
            "tgt_lang": "go",
        })
        # Should echo error about missing src_lang

    def test_missing_tgt_lang(self):
        run_tool_from_spec({
            "tool": "convert_language",
            "path": ".",
            "src_lang": "python",
        })

    def test_single_file_mode(self, tmp_path):
        src = tmp_path / "hello.py"
        src.write_text("print('hi')\n", encoding="utf-8")

        with patch("ai_code.agent.run_language_conversion") as mock_conv, \
             patch("ai_code.agent.typer.confirm", return_value=True):
            mock_conv.return_value = {
                "files": [{"path": "hello.ts", "content": "console.log('hi');\n"}],
                "notes": "done",
            }
            run_tool_from_spec({
                "tool": "convert_language",
                "path": str(src),
                "src_lang": "python",
                "tgt_lang": "typescript",
                "scope": "file",
            })

        # The converted file should be written
        converted = tmp_path / "hello.ts"
        assert converted.exists()
        assert "console.log" in converted.read_text(encoding="utf-8")

    def test_project_mode(self, tmp_path, mock_list_files, mock_read_file_safe):
        src = tmp_path / "app.py"
        src.write_text("x = 1\n", encoding="utf-8")
        mock_list_files.return_value = [src]
        mock_read_file_safe.return_value = "x = 1\n"

        with patch("ai_code.agent.run_language_conversion") as mock_conv, \
             patch("ai_code.agent.typer.confirm", return_value=True):
            mock_conv.return_value = {
                "files": [{"path": "app.go", "content": "package main\n"}],
                "notes": "",
            }
            run_tool_from_spec({
                "tool": "convert_language",
                "path": str(tmp_path),
                "src_lang": "python",
                "tgt_lang": "go",
                "scope": "project",
            })

        output_dir = tmp_path.parent / f"{tmp_path.name}_converted_to_go"
        assert output_dir.exists()


# ===================================================================
# run_tool_from_spec — unknown tool
# ===================================================================

class TestRunToolUnknown:
    """Test that an unknown tool name returns None without error."""

    def test_unknown_tool_returns_none(self):
        result = run_tool_from_spec({"tool": "nonexistent_tool", "path": "."})
        assert result is None
