"""Uninstall command implementation."""

import subprocess
import shutil
import sys
from pathlib import Path
from typing import Optional

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


def uninstall_command(
    force: bool = False,
    dry_run: bool = False,
):
    """
    Uninstall psdfy and remove all related files.
    
    Args:
        force: Skip confirmation prompt
        dry_run: Show what would be removed without actually removing
    """
    print_loading("Uninstalling psdfy...")
    
    config_manager = get_config_manager()
    
    # Items to remove
    items_to_remove = []
    
    # 1. Config directory
    config_dir = config_manager.config_dir
    if config_dir.exists():
        items_to_remove.append(("Config directory", config_dir))
    
    # 2. Weights directory
    weights_dir = config_manager.weights_dir
    if weights_dir.exists():
        items_to_remove.append(("Weights directory", weights_dir))
    
    # 3. Run directory (logs, PID files)
    run_dir = config_manager.run_dir
    if run_dir.exists():
        items_to_remove.append(("Run directory (logs, PIDs)", run_dir))
    
    # Show what will be removed
    print_status("📋", "Items to be removed:")
    for name, path in items_to_remove:
        print_status("  •", f"{name}: {path}")
    
    if dry_run:
        print_status("ℹ️", "(dry-run mode - no changes made)")
        return
    
    # Ask for confirmation if not forced
    if not force:
        print_warning("This will remove all psdfy configuration and data!")
        confirm = input("Are you sure you want to uninstall psdfy? (yes/no): ")
        if confirm.lower() != "yes":
            print_status("ℹ️", "Uninstall cancelled.")
            return
    
    # Stop running services first
    print_loading("Stopping services...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "psdfy", "stop"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            print_success("Services stopped")
        else:
            print_warning("Could not stop services (may not be running)")
    except Exception as e:
        print_warning(f"Error stopping services: {e}")
    
    # Remove directories
    print_loading("Removing files and directories...")
    
    with ProgressBar("🗑️") as progress:
        task_id = create_progress_task(
            progress, "Removing files", total=len(items_to_remove), emoji=""
        )
        
        removed_count = 0
        for name, path in items_to_remove:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                    print_success(f"Removed {name}")
                elif path.is_file():
                    path.unlink()
                    print_success(f"Removed {name}")
                removed_count += 1
                progress.update(task_id, completed=removed_count)
            except Exception as e:
                print_error(f"Error removing {name}: {e}")
    
    # Uninstall pip package
    print_loading("Uninstalling pip package...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "psdfy"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print_success("Pip package uninstalled")
        else:
            print_error(f"Could not uninstall pip package: {result.stderr}")
    except Exception as e:
        print_error(f"Error uninstalling pip package: {e}")
    
    print_success("Uninstall complete!")
    print_status("ℹ️", "To reinstall psdfy later, run:")
    print_status("  ", "pip install psdfy")
