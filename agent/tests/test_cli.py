"""
Tests for AI Infra Monitor Agent CLI

Unit tests for the command-line interface.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
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


@pytest.fixture
def mock_metrics():
    """
    Create mock metrics data fixture.
    
    Returns:
        dict: Mock metrics dictionary
    """
    return {
        "timestamp": "2025-12-01T12:00:00",
        "hostname": "test-host",
        "cpu": {
            "usage_percent": 50.0,
            "cores": 4
        },
        "memory": {
            "total_mb": 8192,
            "used_mb": 4096,
            "usage_percent": 50.0
        }
    }


def test_cli_help(runner):
    """
    Test that --help flag works correctly.
    
    Args:
        runner: Click test runner fixture
    """
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "AI Infra Monitor Agent" in result.output
    assert "run" in result.output


def test_run_command_help(runner):
    """
    Test that run command --help works correctly.
    
    Args:
        runner: Click test runner fixture
    """
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output


@patch("agent.__main__.collect_once")
def test_run_dry_run_mode(mock_collect, runner, mock_metrics):
    """
    Test run command with --dry-run flag.
    
    Args:
        mock_collect: Mocked collect_once function
        runner: Click test runner fixture
        mock_metrics: Mock metrics data
    """
    # Setup mock
    mock_collect.return_value = mock_metrics
    
    # Run command
    result = runner.invoke(cli, ["run", "--dry-run"])
    
    # Assertions
    assert result.exit_code == 0
    mock_collect.assert_called_once()
    
    # Verify JSON output
    output_data = json.loads(result.output)
    assert output_data == mock_metrics


@patch("agent.__main__.collect_once")
def test_run_without_dry_run(mock_collect, runner, mock_metrics):
    """
    Test run command without --dry-run flag.
    
    Args:
        mock_collect: Mocked collect_once function
        runner: Click test runner fixture
        mock_metrics: Mock metrics data
    """
    # Setup mock
    mock_collect.return_value = mock_metrics
    
    # Run command
    result = runner.invoke(cli, ["run"])
    
    # Assertions
    assert result.exit_code == 0
    mock_collect.assert_called_once()
    
    # Verify JSON output
    output_data = json.loads(result.output)
    assert output_data == mock_metrics


@patch("agent.__main__.collect_once")
def test_json_output_structure(mock_collect, runner, mock_metrics):
    """
    Test that JSON output has correct structure.
    
    Args:
        mock_collect: Mocked collect_once function
        runner: Click test runner fixture
        mock_metrics: Mock metrics data
    """
    # Setup mock
    mock_collect.return_value = mock_metrics
    
    # Run command
    result = runner.invoke(cli, ["run", "--dry-run"])
    
    # Parse JSON
    output_data = json.loads(result.output)
    
    # Verify structure
    assert "timestamp" in output_data
    assert "hostname" in output_data
    assert "cpu" in output_data
    assert "memory" in output_data
    assert isinstance(output_data["cpu"], dict)
    assert isinstance(output_data["memory"], dict)


@patch("agent.__main__.collect_once")
def test_error_handling(mock_collect, runner):
    """
    Test error handling when collection fails.
    
    Args:
        mock_collect: Mocked collect_once function
        runner: Click test runner fixture
    """
    # Setup mock to raise exception
    mock_collect.side_effect = Exception("Collection failed")
    
    # Run command
    result = runner.invoke(cli, ["run", "--dry-run"])
    
    # Should exit with error code
    assert result.exit_code == 1
