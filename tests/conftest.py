"""Shared pytest fixtures for agent / CLI tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Temporary project directory with sample files
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with a sample Python file."""
    sample = tmp_path / "sample.py"
    sample.write_text("print('hello')\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Common mocks for ai_code.agent
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_ask_model():
    """Patch ai_code.agent.ask_model."""
    with patch("ai_code.agent.ask_model") as m:
        yield m


@pytest.fixture()
def mock_typer_confirm():
    """Patch ai_code.agent.typer.confirm."""
    with patch("ai_code.agent.typer.confirm") as m:
        yield m


@pytest.fixture()
def mock_typer_echo():
    """Patch ai_code.agent.typer.echo."""
    with patch("ai_code.agent.typer.echo") as m:
        yield m


@pytest.fixture()
def mock_list_files():
    """Patch ai_code.agent.list_files."""
    with patch("ai_code.agent.list_files") as m:
        yield m


@pytest.fixture()
def mock_read_file_safe():
    """Patch ai_code.agent.read_file_safe."""
    with patch("ai_code.agent.read_file_safe") as m:
        yield m
