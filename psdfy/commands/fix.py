"""Fix command implementation for diagnostics and repair."""

import typer
import sys
import os
from pathlib import Path
from typing import Optional
import subprocess

from psdfy.config import get_config_manager
from psdfy.progress_utils import (
    ProgressBar,
    print_status,
    print_success,
    print_error,
    print_warning,
    print_loading,
    create_progress_task,
)


def fix_command(
    reset_password: bool = False,
    reset_client_secret: bool = False,
    redownload_weights: bool = False,
    reset_config: bool = False,
    dry_run: bool = False,
):
    """
    Diagnose and repair psdfy installation.
    
    Args:
        reset_password: Reset UI password to default
        reset_client_secret: Generate new client secret
        redownload_weights: Re-download model weights
        reset_config: Reset config to defaults
        dry_run: Show issues without fixing
    """
    config_manager = get_config_manager()
    
    print_loading("Running psdfy diagnostics...")
    print_status("", "")
    
    issues = []
    
    # Check 1: Python version
    print_status("1️⃣", "Python version:")
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        print_success(f"Python {python_version}")
    else:
        print_error(f"Python {python_version} (requires 3.11+)")
        issues.append("python_version")
    
    # Check 2: Config file
    print_status("2️⃣", "Configuration:")
    if config_manager.config_file.exists():
        print_success(f"Config found: {config_manager.config_file}")
    else:
        print_error(f"Config not found: {config_manager.config_file}")
        issues.append("config_missing")
    
    # Check 3: Weights
    print_status("3️⃣", "Model weights:")
    sam2_weights = config_manager.weights_dir / "sam2_hiera_large.pt"
    if sam2_weights.exists():
        size_mb = sam2_weights.stat().st_size / 1024 / 1024
        print_success(f"SAM 2 weights: {size_mb:.1f}MB")
    else:
        print_error("SAM 2 weights not found")
        issues.append("weights_missing")
    
    # Check 4: Ports
    print_status("4️⃣", "Ports:")
    config = config_manager.load_config()
    api_port = int(config.get("app", {}).get("api_port", 3456))
    ui_port = int(config.get("app", {}).get("ui_port", 3457))
    
    import socket
    
    def is_port_free(port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("localhost", port))
            sock.close()
            return True
        except OSError:
            return False
    
    if is_port_free(api_port):
        print_success(f"API port {api_port} is free")
    else:
        print_warning(f"API port {api_port} is in use")
    
    if is_port_free(ui_port):
        print_success(f"UI port {ui_port} is free")
    else:
        print_warning(f"UI port {ui_port} is in use")
    
    # Check 5: GPU
    print_status("5️⃣", "GPU/Device:")
    try:
        import torch
        if torch.cuda.is_available():
            print_success(f"CUDA available: {torch.cuda.get_device_name(0)}")
        else:
            print_status("ℹ️", "CUDA not available (CPU mode)")
    except ImportError:
        print_status("ℹ️", "PyTorch not installed (CPU mode)")
    
    # Check 6: Service status
    print_status("6️⃣", "Service status:")
    run_dir = config_manager.run_dir
    api_pid_file = run_dir / "api.pid"
    ui_pid_file = run_dir / "ui.pid"
    
    if api_pid_file.exists():
        print_status("ℹ️", "API service PID file exists")
    else:
        print_status("ℹ️", "API service not running")
    
    if ui_pid_file.exists():
        print_status("ℹ️", "UI service PID file exists")
    else:
        print_status("ℹ️", "UI service not running")
    
    # Summary
    print_status("", "=" * 50)
    
    if not issues:
        print_success("All checks passed!")
    else:
        print_warning(f"Found {len(issues)} issue(s)")
        
        if dry_run:
            print_status("ℹ️", "(dry-run mode - no fixes applied)")
        else:
            # Apply fixes
            print_loading("Applying fixes...")
            print_status("", "")
            
            with ProgressBar("🔧") as progress:
                task_id = create_progress_task(
                    progress, "Applying fixes", total=len(issues), emoji=""
                )
                
                fix_count = 0
                
                if "config_missing" in issues and not dry_run:
                    print_status("  ", "Creating default config...")
                    config_content = config_manager.create_default_config()
                    config_manager.save_config(config_content)
                    print_success("Config created")
                    fix_count += 1
                    progress.update(task_id, completed=fix_count)
                
                if "weights_missing" in issues and redownload_weights and not dry_run:
                    print_status("  ", "Downloading weights...")
                    from psdfy.weights import get_weights_downloader
                    downloader = get_weights_downloader(str(config_manager.weights_dir))
                    try:
                        downloader.download_model("sam2", progress_callback=lambda x, y: None)
                        print_success("Weights downloaded")
                        fix_count += 1
                    except Exception as e:
                        print_error(f"Download failed: {e}")
                    progress.update(task_id, completed=fix_count)
                
                if reset_password and not dry_run:
                    print_status("  ", "Resetting password...")
                    config_content = config_manager.create_default_config()
                    config_manager.save_config(config_content)
                    print_success("Password reset to 123456")
                    fix_count += 1
                    progress.update(task_id, completed=fix_count)
                
                if reset_client_secret and not dry_run:
                    print_status("  ", "Generating new client secret...")
                    config = config_manager.load_config()
                    import uuid
                    config["auth"]["client_secret"] = str(uuid.uuid4())
                    print_success("Client secret regenerated")
                    fix_count += 1
                    progress.update(task_id, completed=fix_count)
            
            print_success("Fixes applied!")

