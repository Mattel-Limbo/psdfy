"""Tests for the /capabilities endpoint."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import os


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('app.api_app.routes.convert.settings') as mock:
        yield mock


def test_capabilities_both_models_available(mock_settings):
    """Test capabilities when both SAM2 and DINO are available."""
    from app.api_app.routes.convert import _get_capabilities

    mock_settings.ENABLE_SAM2 = True
    mock_settings.ENABLE_GROUNDING_DINO = True
    mock_settings.SAM2_WEIGHTS_PATH = None
    mock_settings.DINO_WEIGHTS_PATH = None

    with patch('app.api_app.routes.convert.os.path.exists', return_value=True), \
         patch('app.api_app.routes.convert._check_package', return_value=True):
        capabilities = _get_capabilities()

    assert "auto" in capabilities["modes"]
    assert "prompt" in capabilities["modes"]
    assert capabilities["default_mode"] == "auto"
    assert capabilities["sam2_available"] is True
    assert capabilities["dino_available"] is True


def test_capabilities_only_dino_available(mock_settings):
    """Test capabilities when only DINO is available (--no-weights install)."""
    from app.api_app.routes.convert import _get_capabilities

    mock_settings.ENABLE_SAM2 = False
    mock_settings.ENABLE_GROUNDING_DINO = True
    mock_settings.SAM2_WEIGHTS_PATH = None
    mock_settings.DINO_WEIGHTS_PATH = None

    def mock_exists(path):
        return "groundingdino" in str(path)

    with patch('app.api_app.routes.convert.os.path.exists', side_effect=mock_exists), \
         patch('app.api_app.routes.convert._check_package', return_value=True):
        capabilities = _get_capabilities()

    assert "auto" not in capabilities["modes"]
    assert "prompt" in capabilities["modes"]
    assert capabilities["default_mode"] == "prompt"
    assert capabilities["sam2_available"] is False
    assert capabilities["dino_available"] is True


def test_capabilities_no_models_available(mock_settings):
    """Test capabilities when no models are available."""
    from app.api_app.routes.convert import _get_capabilities

    mock_settings.ENABLE_SAM2 = False
    mock_settings.ENABLE_GROUNDING_DINO = False
    mock_settings.SAM2_WEIGHTS_PATH = None
    mock_settings.DINO_WEIGHTS_PATH = None

    with patch('app.api_app.routes.convert.os.path.exists', return_value=False), \
         patch('app.api_app.routes.convert._check_package', return_value=False):
        capabilities = _get_capabilities()

    assert len(capabilities["modes"]) == 0
    assert capabilities["default_mode"] is None
    assert capabilities["sam2_available"] is False
    assert capabilities["dino_available"] is False


def test_capabilities_custom_weights_paths(mock_settings):
    """Test capabilities with custom weights paths."""
    from app.api_app.routes.convert import _get_capabilities

    mock_settings.ENABLE_SAM2 = True
    mock_settings.ENABLE_GROUNDING_DINO = True
    mock_settings.SAM2_WEIGHTS_PATH = "/custom/sam2.pt"
    mock_settings.DINO_WEIGHTS_PATH = "/custom/dino.pth"

    with patch('app.api_app.routes.convert.os.path.exists', return_value=True), \
         patch('app.api_app.routes.convert._check_package', return_value=True):
        capabilities = _get_capabilities()

    assert "auto" in capabilities["modes"]
    assert "prompt" in capabilities["modes"]
