"""Tests for cli.py — Typer REPL entry-point."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from ai_code.cli import app

runner = CliRunner()


class TestCli:
    """Tests for the CLI agent command."""

    def test_exit_command(self):
        result = runner.invoke(app, input="exit\n")
        assert result.exit_code == 0
        assert "종료" in result.output

    def test_quit_command(self):
        result = runner.invoke(app, input="quit\n")
        assert result.exit_code == 0
        assert "종료" in result.output

    def test_empty_input_continues(self):
        result = runner.invoke(app, input="\nexit\n")
        assert result.exit_code == 0
        assert "종료" in result.output

    @patch("ai_code.cli.run_tool_from_spec")
    @patch("ai_code.cli.route_user_request")
    def test_agent_routes_and_executes(self, mock_route, mock_run):
        mock_route.return_value = {"tool": "analyze", "path": "."}
        result = runner.invoke(app, input="analyze my code\nexit\n")
        assert result.exit_code == 0
        mock_route.assert_called_once()
        mock_run.assert_called_once_with({"tool": "analyze", "path": "."})

    @patch("ai_code.cli.route_user_request")
    def test_agent_error_handling(self, mock_route):
        mock_route.side_effect = RuntimeError("API down")
        result = runner.invoke(app, input="do something\nexit\n")
        assert result.exit_code == 0
        assert "에러" in result.output
