"""
Basic test to verify pytest configuration.

This test doesn't depend on any complex fixtures and should run
even with a minimal conftest.py.
"""

import pytest
import os
from pathlib import Path


def test_test_directory_exists():
    """Test that the test directory exists."""
    test_dir = Path(__file__).parent
    assert test_dir.exists(), "Test directory does not exist"
    assert test_dir.is_dir(), "Test path is not a directory"


def test_fixtures_dir_exists():
    """Test that the fixtures directory exists."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    assert fixtures_dir.exists(), "Fixtures directory does not exist"
    assert fixtures_dir.is_dir(), "Fixtures path is not a directory"


def test_data_fixtures_dir_exists():
    """Test that the data fixtures directory exists."""
    data_fixtures_dir = Path(__file__).parent / "data" / "fixtures"
    assert data_fixtures_dir.exists(), "Data fixtures directory does not exist"
    assert data_fixtures_dir.is_dir(), "Data fixtures path is not a directory"


@pytest.mark.parametrize("fixture_file", [
    "users.json",
    "climbs.json",
    "conversations.json"
])
def test_fixture_files_exist(fixture_file):
    """Test that fixture files exist."""
    file_path = Path(__file__).parent / "data" / "fixtures" / fixture_file
    assert file_path.exists(), f"Fixture file does not exist: {fixture_file}"
    assert file_path.is_file(), f"Fixture path is not a file: {fixture_file}" 