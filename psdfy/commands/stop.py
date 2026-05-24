"""Stop command implementation."""

import typer
import subprocess
import signal
import time
from pathlib import Path
from typing import Optional
import sys
import os

from psdfy.config import get_config_manager


def stop_command(
    force: bool = False,
    dry_run: bool = False,
):
    """
    Stop the psdfy service.
    
    Args:
        force: Force kill if graceful shutdown fails
        dry_run: Show what would be done
    """
    config_manager = get_config_manager()
    run_dir = config_manager.run_dir
    
    typer.echo("🛑 Stopping psdfy service...")
    
    # Read PIDs
    api_pid_file = run_dir / "api.pid"
    ui_pid_file = run_dir / "ui.pid"
    
    pids_to_stop = []
    
    if api_pid_file.exists():
        try:
            with open(api_pid_file, "r") as f:
                api_pid = int(f.read().strip())
            pids_to_stop.append(("API", api_pid, api_pid_file))
        except (ValueError, IOError):
            pass
    
    if ui_pid_file.exists():
        try:
            with open(ui_pid_file, "r") as f:
                ui_pid = int(f.read().strip())
            pids_to_stop.append(("UI", ui_pid, ui_pid_file))
        except (ValueError, IOError):
            pass
    
    if not pids_to_stop:
        typer.echo("ℹ️  No running services found")
        return
    
    if dry_run:
        typer.echo("(dry-run mode - would stop:)")
        for name, pid, _ in pids_to_stop:
            typer.echo(f"   {name} (PID {pid})")
        return
    
    # Stop services
    for name, pid, pid_file in pids_to_stop:
        typer.echo(f"\n📍 Stopping {name} (PID {pid})...")
        
        try:
            # Try graceful shutdown first
            if sys.platform == "win32":
                # Windows
                subprocess.run(["taskkill", "/PID", str(pid)], check=False)
            else:
                # Unix
                os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown
            for _ in range(10):
                try:
                    if sys.platform == "win32":
                        # Check if process still exists
                        subprocess.run(
                            ["tasklist", "/FI", f"PID eq {pid}"],
                            capture_output=True,
                            check=True
                        )
                    else:
                        os.kill(pid, 0)  # Check if process exists
                    time.sleep(0.5)
                except (OSError, subprocess.CalledProcessError):
                    # Process terminated
                    break
            
            # Force kill if still running
            if force:
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
                    else:
                        os.kill(pid, signal.SIGKILL)
                    typer.echo(f"   ✓ Force killed")
                except OSError:
                    pass
            else:
                typer.echo(f"   ✓ Stopped")
        
        except Exception as e:
            typer.echo(f"   ✗ Error: {e}", err=True)
        
        # Remove PID file
        try:
            pid_file.unlink()
        except OSError:
            pass
    
    typer.echo("\n✅ Services stopped!")
