"""Tests for naming utilities."""

import pytest
from app.utils.naming import sanitize_layer_name, generate_object_name


def test_sanitize_layer_name_removes_control_chars():
    """Test that control characters are removed."""
    name = "test\x00object\x1f"
    sanitized = sanitize_layer_name(name)
    assert "\x00" not in sanitized
    assert "\x1f" not in sanitized


def test_sanitize_layer_name_replaces_problematic_chars():
    """Test that problematic characters are replaced."""
    name = 'test<object>:name"with|chars'
    sanitized = sanitize_layer_name(name)
    assert "<" not in sanitized
    assert ">" not in sanitized
    assert ":" not in sanitized
    assert '"' not in sanitized
    assert "|" not in sanitized


def test_sanitize_layer_name_truncates_long_names():
    """Test that long names are truncated."""
    name = "a" * 300
    sanitized = sanitize_layer_name(name, max_length=255)
    assert len(sanitized) <= 255


def test_sanitize_layer_name_handles_empty_string():
    """Test that empty strings are handled."""
    sanitized = sanitize_layer_name("")
    assert sanitized == "layer"


def test_generate_object_name_with_label():
    """Test generating object name with label."""
    name = generate_object_name(0, label="person")
    assert name == "person"


def test_generate_object_name_without_label():
    """Test generating object name without label."""
    name = generate_object_name(5)
    assert name == "object_5"


def test_generate_object_name_sanitizes_label():
    """Test that generated names are sanitized."""
    name = generate_object_name(0, label="test<object>")
    assert "<" not in name
    assert ">" not in name
