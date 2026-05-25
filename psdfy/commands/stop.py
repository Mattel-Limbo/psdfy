"""Stop command implementation."""

import typer
import subprocess
import signal
import time
from pathlib import Path
from typing import Optional, List, Tuple
import sys
import os
import socket

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


def get_process_by_port(port: int) -> Optional[int]:
    """Find process PID listening on specific port (Windows only)."""
    if sys.platform != "win32":
        return None
    
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        for line in result.stdout.split('\n'):
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    try:
                        return int(parts[-1])
                    except (ValueError, IndexError):
                        pass
        return None
    except Exception:
        return None


def verify_process_on_port(pid: int, port: int) -> bool:
    """Verify that process is actually listening on the specified port."""
    if sys.platform != "win32":
        return True  # Can't easily verify on Unix, trust the PID file
    
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        for line in result.stdout.split('\n'):
            if f":{port}" in line and "LISTENING" in line and str(pid) in line:
                return True
        return False
    except Exception:
        return True  # If we can't verify, assume it's correct


def is_process_running(pid: int) -> bool:
    """Check if process is still running."""
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return str(pid) in result.stdout
        else:
            os.kill(pid, 0)
            return True
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


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
    
    # Load config to get ports
    config = config_manager.load_config()
    api_port = int(config.get("app", {}).get("api_port", 3456))
    ui_port = int(config.get("app", {}).get("ui_port", 3457))
    
    print_loading("Stopping psdfy service...")
    
    # Read PIDs from files
    api_pid_file = run_dir / "api.pid"
    ui_pid_file = run_dir / "ui.pid"
    
    pids_to_stop: List[Tuple[str, int, int, Path]] = []  # (name, pid, port, pid_file)
    
    # Try to get API PID
    api_pid = None
    if api_pid_file.exists():
        try:
            with open(api_pid_file, "r") as f:
                api_pid = int(f.read().strip())
            
            # Verify it's actually on the right port
            if verify_process_on_port(api_pid, api_port):
                pids_to_stop.append(("API", api_pid, api_port, api_pid_file))
            else:
                print_warning(f"API PID file exists but process not on port {api_port}")
                api_pid = None
        except (ValueError, IOError):
            pass
    
    # If no PID file or verification failed, try to find by port
    if api_pid is None:
        found_pid = get_process_by_port(api_port)
        if found_pid:
            print_status("ℹ️", f"Found API process on port {api_port} (PID {found_pid})")
            pids_to_stop.append(("API", found_pid, api_port, api_pid_file))
    
    # Try to get UI PID
    ui_pid = None
    if ui_pid_file.exists():
        try:
            with open(ui_pid_file, "r") as f:
                ui_pid = int(f.read().strip())
            
            # Verify it's actually on the right port
            if verify_process_on_port(ui_pid, ui_port):
                pids_to_stop.append(("UI", ui_pid, ui_port, ui_pid_file))
            else:
                print_warning(f"UI PID file exists but process not on port {ui_port}")
                ui_pid = None
        except (ValueError, IOError):
            pass
    
    # If no PID file or verification failed, try to find by port
    if ui_pid is None:
        found_pid = get_process_by_port(ui_port)
        if found_pid:
            print_status("ℹ️", f"Found UI process on port {ui_port} (PID {found_pid})")
            pids_to_stop.append(("UI", found_pid, ui_port, ui_pid_file))
    
    if not pids_to_stop:
        print_status("ℹ️", "No running services found on ports 3456 or 3457")
        return
    
    if dry_run:
        print_status("ℹ️", "(dry-run mode - would stop:)")
        for name, pid, port, _ in pids_to_stop:
            print_status("  ", f"{name} (PID {pid}) on port {port}")
        return
    
    # Stop services with progress
    with ProgressBar("🛑") as progress:
        for idx, (name, pid, port, pid_file) in enumerate(pids_to_stop):
            task_id = create_progress_task(
                progress, f"Stopping {name} (PID {pid})", total=10, emoji=""
            )
            
            print_status("🔍", f"Stopping {name} (PID {pid}) on port {port}...")
            
            try:
                # Try graceful shutdown first
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(pid)],
                        capture_output=True,
                        timeout=5,
                        check=False
                    )
                else:
                    os.kill(pid, signal.SIGTERM)
                
                # Wait for graceful shutdown (up to 5 seconds)
                for i in range(10):
                    if not is_process_running(pid):
                        print_success(f"{name} stopped gracefully")
                        progress.update(task_id, completed=10)
                        break
                    progress.update(task_id, completed=i + 1)
                    time.sleep(0.5)
                else:
                    # Process still running after graceful attempt
                    print_warning(f"Graceful shutdown timeout, force killing {name}...")
                    
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
                            print_success(f"{name} force killed")
                            progress.update(task_id, completed=10)
                        else:
                            print_error(f"Could not terminate {name} process")
                    except Exception as e:
                        print_error(f"Force kill failed: {e}")
            
            except Exception as e:
                print_error(f"Error stopping {name}: {e}")
            
            # Remove PID file
            try:
                pid_file.unlink()
            except OSError:
                pass
    
    print_success("Services stopped!")

