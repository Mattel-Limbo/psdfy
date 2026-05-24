"""Start command implementation."""

import typer
import subprocess
import time
import socket
from pathlib import Path
from typing import Optional, List
import sys
import os

from psdfy.config import get_config_manager


def is_port_free(host: str, port: int) -> bool:
    """Check if port is free."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, port))
        sock.close()
        return True
    except OSError:
        return False


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


def kill_process_by_port(port: int) -> bool:
    """Kill process listening on specific port."""
    if sys.platform != "win32":
        return False
    
    pid = get_process_by_port(port)
    if not pid:
        return False
    
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            timeout=5,
            check=False
        )
        time.sleep(0.5)
        return not get_process_by_port(port)
    except Exception:
        return False


def wait_for_health(host: str, port: int, timeout: int = 30) -> bool:
    """Wait for service to be healthy."""
    import urllib.request
    import urllib.error
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2)
            if response.status == 200:
                return True
        except (urllib.error.URLError, Exception):
            pass
        
        time.sleep(0.5)
    
    return False


def start_command(
    host: Optional[str] = None,
    api_port: Optional[int] = None,
    ui_port: Optional[int] = None,
    foreground: bool = False,
    dry_run: bool = False,
):
    """
    Start the psdfy service.
    
    Args:
        host: Override API host
        api_port: Override API port
        ui_port: Override UI port
        foreground: Run in foreground
        dry_run: Show what would be done
    """
    config_manager = get_config_manager()
    
    # Load config
    config = config_manager.load_config()
    
    # Use provided values or defaults from config
    if host is None:
        host = config.get("app", {}).get("host", "localhost")
    if api_port is None:
        api_port = int(config.get("app", {}).get("api_port", 3456))
    if ui_port is None:
        ui_port = int(config.get("app", {}).get("ui_port", 3457))
    
    typer.echo("🚀 Starting psdfy service...")
    
    # Check if ports are already in use
    api_free = is_port_free(host, api_port)
    ui_free = is_port_free(host, ui_port)
    
    if not api_free or not ui_free:
        typer.echo("\n⚠️  Ports already in use:")
        if not api_free:
            typer.echo(f"   API port {api_port} is in use")
        if not ui_free:
            typer.echo(f"   UI port {ui_port} is in use")
        
        # Try to kill existing processes on these ports
        typer.echo("\n🔄 Attempting to kill existing processes...")
        
        killed_api = False
        killed_ui = False
        
        if not api_free:
            if kill_process_by_port(api_port):
                typer.echo(f"   ✓ Killed process on port {api_port}")
                killed_api = True
            else:
                typer.echo(f"   ✗ Could not kill process on port {api_port}")
        
        if not ui_free:
            if kill_process_by_port(ui_port):
                typer.echo(f"   ✓ Killed process on port {ui_port}")
                killed_ui = True
            else:
                typer.echo(f"   ✗ Could not kill process on port {ui_port}")
        
        # Check again if ports are free
        time.sleep(1)
        if not is_port_free(host, api_port) or not is_port_free(host, ui_port):
            typer.echo("\n✗ Could not free ports. Please manually stop the services.", err=True)
            return
    
    # Pre-flight checks
    typer.echo("\n✓ Pre-flight checks:")
    typer.echo(f"   Ports free: {host}:{api_port}, {host}:{ui_port}")
    
    # Check weights
    weights_dir = config_manager.weights_dir
    sam2_weights = weights_dir / "sam2_hiera_large.pt"
    if not sam2_weights.exists():
        typer.echo("   ⚠️  SAM 2 weights not found. Run 'psdfy install' first.", err=True)
        return
    typer.echo(f"   Weights: OK")
    
    if dry_run:
        typer.echo("\n(dry-run mode - no changes made)")
        return
    
    # Start servers
    typer.echo("\n📡 Starting servers...")
    
    # Create run directory
    run_dir = config_manager.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Get project root (parent of psdfy package)
    project_root = Path(__file__).parent.parent.parent
    
    # Prepare environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    
    # Start API server
    api_log = run_dir / "api.log"
    api_pid_file = run_dir / "api.pid"
    
    typer.echo(f"   Starting API server on {host}:{api_port}...")
    
    if foreground:
        # Run in foreground
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "uvicorn",
                    "app.main:api_app",
                    "--host", host,
                    "--port", str(api_port),
                ],
                cwd=str(project_root),
                env=env,
            )
        except KeyboardInterrupt:
            typer.echo("\nShutdown requested")
    else:
        # Run in background
        with open(api_log, "w") as log_file:
            api_process = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "app.main:api_app",
                    "--host", host,
                    "--port", str(api_port),
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(project_root),
                env=env,
            )
        
        # Save PID
        with open(api_pid_file, "w") as f:
            f.write(str(api_process.pid))
        
        # Start UI server
        ui_log = run_dir / "ui.log"
        ui_pid_file = run_dir / "ui.pid"
        
        typer.echo(f"   Starting UI server on {host}:{ui_port}...")
        
        with open(ui_log, "w") as log_file:
            ui_process = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "app.main:ui_app",
                    "--host", host,
                    "--port", str(ui_port),
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(project_root),
                env=env,
            )
        
        # Save PID
        with open(ui_pid_file, "w") as f:
            f.write(str(ui_process.pid))
        
        # Wait for health
        typer.echo("\n⏳ Waiting for services to be ready...")
        
        if wait_for_health(host, api_port):
            typer.echo(f"   ✓ API ready: http://{host}:{api_port}")
        else:
            typer.echo(f"   ✗ API failed to start", err=True)
            # Show error log
            if api_log.exists():
                typer.echo(f"\n   API Log ({api_log}):", err=True)
                with open(api_log) as f:
                    for line in f.readlines()[-10:]:
                        typer.echo(f"   {line.rstrip()}", err=True)
        
        if wait_for_health(host, ui_port):
            typer.echo(f"   ✓ UI ready: http://{host}:{ui_port}")
        else:
            typer.echo(f"   ✗ UI failed to start", err=True)
            # Show error log
            if ui_log.exists():
                typer.echo(f"\n   UI Log ({ui_log}):", err=True)
                with open(ui_log) as f:
                    for line in f.readlines()[-10:]:
                        typer.echo(f"   {line.rstrip()}", err=True)
        
        typer.echo("\n✅ Services started!")
        typer.echo(f"\nOpen your browser: http://{host}:{ui_port}")
