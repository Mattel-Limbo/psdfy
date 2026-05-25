"""Uninstall command implementation."""

import typer
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Optional

from psdfy.config import get_config_manager


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
    typer.echo("ðŸ—‘ï¸  Uninstalling psdfy...")
    
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
    typer.echo("\nðŸ“‹ Items to be removed:")
    for name, path in items_to_remove:
        typer.echo(f"   â€¢ {name}: {path}")
    
    if dry_run:
        typer.echo("\n(dry-run mode - no changes made)")
        return
    
    # Ask for confirmation if not forced
    if not force:
        typer.echo("\nâš ï¸  This will remove all psdfy configuration and data!")
        confirm = typer.confirm("Are you sure you want to uninstall psdfy?")
        if not confirm:
            typer.echo("Uninstall cancelled.")
            return
    
    # Stop running services first
    typer.echo("\nðŸ›‘ Stopping services...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "psdfy", "stop"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            typer.echo("   âœ“ Services stopped")
        else:
            typer.echo("   âš ï¸  Could not stop services (may not be running)")
    except Exception as e:
        typer.echo(f"   âš ï¸  Error stopping services: {e}")
    
    # Remove directories
    typer.echo("\nðŸ—‘ï¸  Removing files and directories...")
    for name, path in items_to_remove:
        try:
            if path.is_dir():
                shutil.rmtree(path)
                typer.echo(f"   âœ“ Removed {name}")
            elif path.is_file():
                path.unlink()
                typer.echo(f"   âœ“ Removed {name}")
        except Exception as e:
            typer.echo(f"   âœ— Error removing {name}: {e}", err=True)
    
    # Uninstall pip package
    typer.echo("\nðŸ“¦ Uninstalling pip package...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "psdfy"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            typer.echo("   âœ“ Pip package uninstalled")
        else:
            typer.echo(f"   âš ï¸  Could not uninstall pip package: {result.stderr}")
    except Exception as e:
        typer.echo(f"   âœ— Error uninstalling pip package: {e}", err=True)
    
    typer.echo("\nâœ… Uninstall complete!")
    typer.echo("\nTo reinstall psdfy later, run:")
    typer.echo("   pip install psdfy")

