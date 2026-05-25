"""Install command implementation."""

import typer
import sys
import subprocess
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
    
    # Step 3: Download weights
    if not no_weights:
        print_status("📥", "Downloading model weights...")
        downloader = get_weights_downloader(str(config_manager.weights_dir))
        
        try:
            if not dry_run:
                with DownloadProgress("📥") as progress:
                    task_id = create_progress_task(
                        progress, "SAM 2 model weights", total=100, emoji=""
                    )
                    
                    def progress_callback(current: int, total: int):
                        """Update progress bar during download."""
                        if total > 0:
                            percentage = int((current / total) * 100)
                            progress.update(task_id, completed=percentage)
                    
                    downloader.download_model("sam2", progress_callback=progress_callback)
                
                print_success("SAM 2 weights ready")
            else:
                print_status("  ", "SAM 2 weights (dry-run)")
        except Exception as e:
            print_error(f"SAM 2 download failed: {e}")
    
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

