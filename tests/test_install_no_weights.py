"""Tests for install command with --no-weights flag."""

import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
import tempfile
import os


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_install_no_weights_downloads_dino(temp_config_dir):
    """Test that --no-weights still downloads GroundingDINO."""
    from psdfy.commands.install import install_command
    
    with patch('psdfy.commands.install.get_config_manager') as mock_config_mgr, \
         patch('psdfy.commands.install.get_weights_downloader') as mock_downloader_factory, \
         patch('psdfy.commands.install.print_status'), \
         patch('psdfy.commands.install.print_success'), \
         patch('psdfy.commands.install.print_warning'), \
         patch('psdfy.commands.install.print_error'), \
         patch('psdfy.commands.install.print_loading'), \
         patch('psdfy.commands.install.DownloadProgress'), \
         patch('psdfy.commands.install.create_progress_task'), \
         patch('subprocess.run'):
        
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_dir = Path(temp_config_dir)
        mock_config.weights_dir = Path(temp_config_dir) / "weights"
        mock_config.outputs_dir = Path(temp_config_dir) / "outputs"
        mock_config.run_dir = Path(temp_config_dir) / "run"
        mock_config_mgr.return_value = mock_config
        
        mock_downloader = MagicMock()
        mock_downloader_factory.return_value = mock_downloader
        
        # Run install with --no-weights
        install_command(
            password="test123",
            no_weights=True,
            dry_run=False
        )
        
        # Verify GroundingDINO was downloaded
        calls = mock_downloader.download_model.call_args_list
        model_names = [call[0][0] for call in calls]
        
        assert "groundingdino" in model_names
        assert "sam2" not in model_names


def test_install_no_weights_sets_config_flags(temp_config_dir):
    """Test that --no-weights sets correct config flags."""
    from psdfy.commands.install import install_command
    from psdfy.config import ConfigManager
    
    with patch('psdfy.commands.install.get_weights_downloader'), \
         patch('psdfy.commands.install.print_status'), \
         patch('psdfy.commands.install.print_success'), \
         patch('psdfy.commands.install.print_warning'), \
         patch('psdfy.commands.install.print_error'), \
         patch('psdfy.commands.install.print_loading'), \
         patch('psdfy.commands.install.DownloadProgress'), \
         patch('psdfy.commands.install.create_progress_task'), \
         patch('subprocess.run'):
        
        # Create real config manager with temp dir
        config_mgr = ConfigManager(config_dir=temp_config_dir)
        
        with patch('psdfy.commands.install.get_config_manager', return_value=config_mgr):
            install_command(
                password="test123",
                no_weights=True,
                dry_run=False
            )
        
        # Load and verify config
        config = config_mgr.load_config()
        
        assert config["models"]["enable_sam2"] is False
        assert config["models"]["enable_grounding_dino"] is True


def test_install_full_downloads_both_models(temp_config_dir):
    """Test that full install downloads both SAM2 and GroundingDINO."""
    from psdfy.commands.install import install_command
    
    with patch('psdfy.commands.install.get_config_manager') as mock_config_mgr, \
         patch('psdfy.commands.install.get_weights_downloader') as mock_downloader_factory, \
         patch('psdfy.commands.install.print_status'), \
         patch('psdfy.commands.install.print_success'), \
         patch('psdfy.commands.install.print_warning'), \
         patch('psdfy.commands.install.print_error'), \
         patch('psdfy.commands.install.print_loading'), \
         patch('psdfy.commands.install.DownloadProgress'), \
         patch('psdfy.commands.install.create_progress_task'), \
         patch('subprocess.run'):
        
        # Setup mocks
        mock_config = MagicMock()
        mock_config.config_dir = Path(temp_config_dir)
        mock_config.weights_dir = Path(temp_config_dir) / "weights"
        mock_config.outputs_dir = Path(temp_config_dir) / "outputs"
        mock_config.run_dir = Path(temp_config_dir) / "run"
        mock_config_mgr.return_value = mock_config
        
        mock_downloader = MagicMock()
        mock_downloader_factory.return_value = mock_downloader
        
        # Run install without --no-weights
        install_command(
            password="test123",
            no_weights=False,
            dry_run=False
        )
        
        # Verify both models were downloaded
        calls = mock_downloader.download_model.call_args_list
        model_names = [call[0][0] for call in calls]
        
        assert "sam2" in model_names
        assert "groundingdino" in model_names
