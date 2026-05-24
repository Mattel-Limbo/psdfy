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
    
    def is_process_running(pid: int) -> bool:
        """Check if process is still running."""
        try:
            if sys.platform == "win32":
                # Windows: use tasklist to check
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # If PID is in output, process is running
                return str(pid) in result.stdout
            else:
                # Unix: send signal 0 to check
                os.kill(pid, 0)
                return True
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
    
    # Stop services
    for name, pid, pid_file in pids_to_stop:
        typer.echo(f"\n📍 Stopping {name} (PID {pid})...")
        
        try:
            # Try graceful shutdown first
            if sys.platform == "win32":
                # Windows: taskkill without /F for graceful shutdown
                subprocess.run(
                    ["taskkill", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                    check=False
                )
            else:
                # Unix: SIGTERM for graceful shutdown
                os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown (up to 5 seconds)
            for i in range(10):
                if not is_process_running(pid):
                    typer.echo(f"   ✓ Stopped gracefully")
                    break
                time.sleep(0.5)
            else:
                # Process still running after graceful attempt
                typer.echo(f"   ⚠️  Graceful shutdown timeout, force killing...")
                
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/PID", str(pid), "/F"],
                            capture_output=True,
                            timeout=5,
                            check=False
                        )
                    else:
                        os.kill(pid, signal.SIGKILL)
                    
                    # Verify it's dead
                    time.sleep(0.5)
                    if not is_process_running(pid):
                        typer.echo(f"   ✓ Force killed")
                    else:
                        typer.echo(f"   ✗ Could not terminate process", err=True)
                except Exception as e:
                    typer.echo(f"   ✗ Force kill failed: {e}", err=True)
        
        except Exception as e:
            typer.echo(f"   ✗ Error: {e}", err=True)
        
        # Remove PID file
        try:
            pid_file.unlink()
        except OSError:
            pass
    
    typer.echo("\n✅ Services stopped!")
