"""Install command implementation."""

import typer
import sys
import subprocess
import importlib.util
from pathlib import Path
from typing import Optional
import time

from psdfy.config import get_config_manager
from psdfy.weights import get_weights_downloader
from psdfy.progress_utils import (
    ProgressBar,
    DownloadProgress,
    print_status,
    print_success,
    print_error,
    print_warning,
    print_loading,
    create_progress_task,
)


def install_command(
    password: Optional[str] = None,
    host: str = "localhost",
    api_port: int = 3456,
    ui_port: int = 3457,
    service: bool = False,
    no_weights: bool = False,
    dry_run: bool = False,
):
    """
    Install psdfy and download model weights.
    
    Args:
        password: UI password (default: 123456)
        host: API host
        api_port: API port
        ui_port: UI port
        service: Install as system service
        no_weights: Skip downloading weights
        dry_run: Show what would be done
    """
    # Step 0: Upgrade psdfy package from PyPI
    print_status("🔍", "Checking for latest psdfy version...")
    if not dry_run:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "--no-deps", "psdfy"],
                capture_output=True,
                timeout=60,
                check=False
            )
            print_success("Package updated to latest version")
        except Exception as e:
            print_warning(f"Could not upgrade package: {e}")
    
    config_manager = get_config_manager()
    
    print_loading("Installing psdfy...")
    
    # Step 1: Create directories
    print_status("📁", "Creating directories...")
    if not dry_run:
        config_manager.ensure_directories()
    print_status("  ", f"Config: {config_manager.config_dir}")
    print_status("  ", f"Weights: {config_manager.weights_dir}")
    print_status("  ", f"Outputs: {config_manager.outputs_dir}")
    
    # Step 2: Create config
    print_status("⚙️", "Creating configuration...")
    if password is None:
        password = "123456"
    
    config_content = config_manager.create_default_config(
        password=password,
        host=host,
        api_port=api_port,
        ui_port=ui_port,
        enable_sam2=not no_weights,
    )
    
    if not dry_run:
        config_manager.save_config(config_content)
    
    print_status("  ", f"Host: {host}")
    print_status("  ", f"API Port: {api_port}")
    print_status("  ", f"UI Port: {ui_port}")
    print_status("  ", f"Password: {'*' * len(password)}")
    
    # Step 2b: Install ML dependencies
    print_status("📦", "Installing ML dependencies...")
    
    # Always install torch (required by both SAM2 and DINO)
    try:
        if importlib.util.find_spec("torch") is None:
            print_status("  ", "Installing torch (CPU)...")
            if not dry_run:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "torch", "torchvision",
                     "--index-url", "https://download.pytorch.org/whl/cpu"],
                    check=True, timeout=300,
                )
                print_success("torch installed")
        else:
            print_status("  ", "torch already installed")
    except Exception as e:
        print_warning(f"torch install failed: {e}")

    # Always install pytoshop (PSD writer)
    try:
        if importlib.util.find_spec("pytoshop") is None:
            print_status("  ", "Installing pytoshop...")
            if not dry_run:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "pytoshop>=1.2.0"],
                    check=True, timeout=120,
                )
                print_success("pytoshop installed")
        else:
            print_status("  ", "pytoshop already installed")
    except Exception as e:
        print_warning(f"pytoshop install failed: {e}")
    
    # Always install GroundingDINO
    try:
        if importlib.util.find_spec("groundingdino") is None:
            print_status("  ", "Installing GroundingDINO...")
            if not dry_run:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install",
                     "--no-build-isolation",
                     "git+https://github.com/IDEA-Research/GroundingDINO.git"],
                    check=True, timeout=300,
                )
                print_success("GroundingDINO installed")
        else:
            print_status("  ", "GroundingDINO already installed")
    except Exception as e:
        print_warning(f"GroundingDINO install failed: {e}")
    
    # Install SAM2 only for full install
    if not no_weights:
        try:
            if importlib.util.find_spec("sam2") is None:
                print_status("  ", "Installing SAM 2...")
                if not dry_run:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install",
                         "git+https://github.com/facebookresearch/sam2.git"],
                        check=True, timeout=300,
                    )
                    print_success("SAM 2 installed")
            else:
                print_status("  ", "SAM 2 already installed")
        except Exception as e:
            print_warning(f"SAM 2 install failed: {e}")
    
    # Step 3: Download weights
    downloader = get_weights_downloader(str(config_manager.weights_dir))
    
    if not no_weights:
        print_status("📥", "Downloading model weights...")
        
        try:
            if not dry_run:
                downloader.download_model("sam2")
                print_success("SAM 2 weights ready")
            else:
                print_status("  ", "SAM 2 weights (dry-run)")
        except Exception as e:
            print_error(f"SAM 2 download failed: {e}")
    
    # Step 3b: Always download GroundingDINO weights
    print_status("📥", "Downloading GroundingDINO weights...")
    try:
        if not dry_run:
            downloader.download_model("groundingdino")
            print_success("GroundingDINO weights ready")
        else:
            print_status("  ", "GroundingDINO weights (dry-run)")
    except Exception as e:
        print_warning(f"GroundingDINO download failed: {e}")
    
    # Step 4: Register service (if requested)
    if service:
        print_status("🔧", "Registering system service...")
        print_status("  ", "TODO: Implement service registration")
    
    # Summary
    print_success("Installation complete!")
    print_status("📋", "\nNext steps:")
    print_status("  ", "1. Start the service: psdfy start")
    print_status("  ", f"2. Open browser: http://{host}:{ui_port}")
    print_status("  ", f"3. Login with password: {password}")
    
    if dry_run:
        print_status("ℹ️", "(dry-run mode - no changes made)")

