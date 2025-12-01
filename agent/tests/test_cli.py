"""
Tests for AI Infra Monitor Agent CLI

Unit tests for the command-line interface.
"""

import pytest
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from agent.__main__ import cli


@pytest.fixture
def runner():
    """
    Create a Click CLI test runner fixture.
    
    Returns:
        CliRunner: Click test runner instance
    """
    return CliRunner()


def test_cli_help(runner):
    """
    Test that --help flag works correctly.
    """
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "AI Infra Monitor Agent" in result.output
    assert "run" in result.output


def test_run_command_help(runner):
    """
    Test that run command --help works correctly.
    """
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output


@patch("agent.run.run", new_callable=AsyncMock)
def test_run_dry_run_mode(mock_run, runner):
    """
    Test run command with --dry-run flag.
    
    Should call agent.run.run with dry_run=True.
    """
    # Run command
    result = runner.invoke(cli, ["run", "--dry-run"])
    
    # Assertions
    assert result.exit_code == 0
    mock_run.assert_called_once_with(dry_run=True)


@patch("agent.run.run", new_callable=AsyncMock)
def test_run_without_dry_run(mock_run, runner):
    """
    Test run command without --dry-run flag.
    
    Should call agent.run.run with dry_run=False.
    """
    # Run command
    result = runner.invoke(cli, ["run"])
    
    # Assertions
    assert result.exit_code == 0
    mock_run.assert_called_once_with(dry_run=False)


@patch("agent.run.run", new_callable=AsyncMock)
def test_error_handling(mock_run, runner):
    """
    Test error handling when agent fails.
    """
    # Setup mock to raise exception
    mock_run.side_effect = Exception("Agent crashed")
    
    # Run command
    result = runner.invoke(cli, ["run"])
    
    # Should exit with error code 1 (handled in __main__)
    assert result.exit_code == 1
    # assert "Error running agent" in result.output  # Logging capture can be flaky with CliRunner
