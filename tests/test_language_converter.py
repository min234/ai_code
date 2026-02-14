"""Tests for core.language_converter module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_code.core.language_converter import (
    ConversionResult,
    ProjectFile,
    ProjectSnapshot,
    _build_files_block,
    _build_user_prompt,
    run_language_conversion,
)


# ---------------------------------------------------------------------------
# _build_files_block
# ---------------------------------------------------------------------------

class TestBuildFilesBlock:
    """Tests for _build_files_block."""

    def test_empty_files(self):
        snapshot: ProjectSnapshot = {"root": "src", "files": []}
        result = _build_files_block(snapshot)
        assert result == ""

    def test_missing_files_key(self):
        snapshot: ProjectSnapshot = {"root": "src", "files": []}
        # Simulate missing key by using a plain dict
        result = _build_files_block({})  # type: ignore[arg-type]
        assert result == ""

    def test_single_file(self):
        file_: ProjectFile = {
            "path": "main.py",
            "language": "python",
            "content": "print('hello')",
        }
        snapshot: ProjectSnapshot = {"root": "src", "files": [file_]}
        result = _build_files_block(snapshot)
        assert "FILE: main.py" in result
        assert "LANG: python" in result
        assert "print('hello')" in result

    def test_multiple_files(self):
        files = [
            ProjectFile(path="a.py", language="python", content="# a"),
            ProjectFile(path="b.py", language="python", content="# b"),
        ]
        snapshot: ProjectSnapshot = {"root": ".", "files": files}
        result = _build_files_block(snapshot)
        assert result.count("FILE:") == 2
        assert "FILE: a.py" in result
        assert "FILE: b.py" in result

    def test_default_language_unknown(self):
        file_: dict = {"path": "x.rs", "content": "fn main() {}"}
        snapshot: ProjectSnapshot = {"root": ".", "files": [file_]}  # type: ignore[list-item]
        result = _build_files_block(snapshot)
        assert "LANG: unknown" in result


# ---------------------------------------------------------------------------
# _build_user_prompt
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:
    """Tests for _build_user_prompt."""

    def _make_snapshot(self, *, summary: str | None = None) -> ProjectSnapshot:
        file_: ProjectFile = {
            "path": "app.py",
            "language": "python",
            "content": "pass",
        }
        snap: ProjectSnapshot = {"root": ".", "files": [file_]}
        if summary is not None:
            snap["summary"] = summary
        return snap

    def test_contains_languages(self):
        prompt = _build_user_prompt(
            self._make_snapshot(),
            src_lang="Python",
            tgt_lang="TypeScript",
            target_stack_desc="Node.js",
        )
        assert "Python" in prompt
        assert "TypeScript" in prompt

    def test_contains_stack_desc(self):
        prompt = _build_user_prompt(
            self._make_snapshot(),
            src_lang="Python",
            tgt_lang="Go",
            target_stack_desc="Go 1.22 stdlib",
        )
        assert "Go 1.22 stdlib" in prompt

    def test_summary_included(self):
        prompt = _build_user_prompt(
            self._make_snapshot(summary="A web server"),
            src_lang="Python",
            tgt_lang="Rust",
            target_stack_desc="Actix-web",
        )
        assert "A web server" in prompt

    def test_no_summary_fallback(self):
        prompt = _build_user_prompt(
            self._make_snapshot(),
            src_lang="Python",
            tgt_lang="Java",
            target_stack_desc="Spring Boot",
        )
        assert "(no summary provided)" in prompt

    def test_files_block_embedded(self):
        prompt = _build_user_prompt(
            self._make_snapshot(),
            src_lang="Python",
            tgt_lang="TypeScript",
            target_stack_desc="Deno",
        )
        assert "FILE: app.py" in prompt


# ---------------------------------------------------------------------------
# run_language_conversion
# ---------------------------------------------------------------------------

class TestRunLanguageConversion:
    """Tests for run_language_conversion."""

    _SNAPSHOT: ProjectSnapshot = {
        "root": ".",
        "files": [
            ProjectFile(path="main.py", language="python", content="print(1)"),
        ],
    }

    @patch("ai_code.core.language_converter.ask_model")
    def test_successful_conversion(self, mock_ask):
        mock_ask.return_value = {
            "files": [{"path": "main.ts", "content": "console.log(1)"}],
            "notes": "변환 완료",
        }
        result: ConversionResult = run_language_conversion(
            self._SNAPSHOT,
            src_lang="Python",
            tgt_lang="TypeScript",
            target_stack_desc="Node.js",
        )
        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "main.ts"
        assert result["notes"] == "변환 완료"

    @patch("ai_code.core.language_converter.ask_model")
    def test_non_dict_response_raises(self, mock_ask):
        mock_ask.return_value = "not a dict"
        with pytest.raises(TypeError, match="did not return a valid JSON"):
            run_language_conversion(
                self._SNAPSHOT,
                src_lang="Python",
                tgt_lang="Go",
                target_stack_desc="stdlib",
            )

    @patch("ai_code.core.language_converter.ask_model")
    def test_filters_invalid_files(self, mock_ask):
        mock_ask.return_value = {
            "files": [
                {"path": "good.ts", "content": "ok"},
                {"path": 123, "content": "bad path"},
                {"path": "no_content.ts"},
            ],
            "notes": "",
        }
        result = run_language_conversion(
            self._SNAPSHOT,
            src_lang="Python",
            tgt_lang="TypeScript",
            target_stack_desc="Node.js",
        )
        assert len(result["files"]) == 1
        assert result["files"][0]["path"] == "good.ts"

    @patch("ai_code.core.language_converter.ask_model")
    def test_notes_coerced_to_string(self, mock_ask):
        mock_ask.return_value = {
            "files": [],
            "notes": 42,
        }
        result = run_language_conversion(
            self._SNAPSHOT,
            src_lang="Python",
            tgt_lang="Rust",
            target_stack_desc="tokio",
        )
        assert result["notes"] == "42"

    @patch("ai_code.core.language_converter.ask_model")
    def test_empty_files_in_response(self, mock_ask):
        mock_ask.return_value = {"files": [], "notes": "nothing to convert"}
        result = run_language_conversion(
            self._SNAPSHOT,
            src_lang="Python",
            tgt_lang="C",
            target_stack_desc="GCC",
        )
        assert result["files"] == []
        assert result["notes"] == "nothing to convert"

    @patch("ai_code.core.language_converter.ask_model")
    def test_model_param_forwarded(self, mock_ask):
        mock_ask.return_value = {"files": [], "notes": ""}
        run_language_conversion(
            self._SNAPSHOT,
            src_lang="Python",
            tgt_lang="Java",
            target_stack_desc="Spring",
            model="gpt-4o-mini",
        )
        _, kwargs = mock_ask.call_args
        assert kwargs["model"] == "gpt-4o-mini"
