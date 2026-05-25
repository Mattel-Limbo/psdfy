"""Fix command implementation for diagnostics and repair."""

import typer
import sys
import os
from pathlib import Path
from typing import Optional
import subprocess

from psdfy.config import get_config_manager


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
    
    typer.echo("ðŸ” Running psdfy diagnostics...\n")
    
    issues = []
    
    # Check 1: Python version
    typer.echo("1ï¸âƒ£  Python version:")
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        typer.echo(f"   âœ“ Python {python_version}")
    else:
        typer.echo(f"   âœ— Python {python_version} (requires 3.11+)")
        issues.append("python_version")
    
    # Check 2: Config file
    typer.echo("\n2ï¸âƒ£  Configuration:")
    if config_manager.config_file.exists():
        typer.echo(f"   âœ“ Config found: {config_manager.config_file}")
    else:
        typer.echo(f"   âœ— Config not found: {config_manager.config_file}")
        issues.append("config_missing")
    
    # Check 3: Weights
    typer.echo("\n3ï¸âƒ£  Model weights:")
    sam2_weights = config_manager.weights_dir / "sam2_hiera_large.pt"
    if sam2_weights.exists():
        size_mb = sam2_weights.stat().st_size / 1024 / 1024
        typer.echo(f"   âœ“ SAM 2 weights: {size_mb:.1f}MB")
    else:
        typer.echo(f"   âœ— SAM 2 weights not found")
        issues.append("weights_missing")
    
    # Check 4: Ports
    typer.echo("\n4ï¸âƒ£  Ports:")
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
        typer.echo(f"   âœ“ API port {api_port} is free")
    else:
        typer.echo(f"   âš ï¸  API port {api_port} is in use")
    
    if is_port_free(ui_port):
        typer.echo(f"   âœ“ UI port {ui_port} is free")
    else:
        typer.echo(f"   âš ï¸  UI port {ui_port} is in use")
    
    # Check 5: GPU
    typer.echo("\n5ï¸âƒ£  GPU/Device:")
    try:
        import torch
        if torch.cuda.is_available():
            typer.echo(f"   âœ“ CUDA available: {torch.cuda.get_device_name(0)}")
        else:
            typer.echo(f"   â„¹ï¸  CUDA not available (CPU mode)")
    except ImportError:
        typer.echo(f"   â„¹ï¸  PyTorch not installed (CPU mode)")
    
    # Check 6: Service status
    typer.echo("\n6ï¸âƒ£  Service status:")
    run_dir = config_manager.run_dir
    api_pid_file = run_dir / "api.pid"
    ui_pid_file = run_dir / "ui.pid"
    
    if api_pid_file.exists():
        typer.echo(f"   â„¹ï¸  API service PID file exists")
    else:
        typer.echo(f"   â„¹ï¸  API service not running")
    
    if ui_pid_file.exists():
        typer.echo(f"   â„¹ï¸  UI service PID file exists")
    else:
        typer.echo(f"   â„¹ï¸  UI service not running")
    
    # Summary
    typer.echo("\n" + "=" * 50)
    
    if not issues:
        typer.echo("âœ… All checks passed!")
    else:
        typer.echo(f"âš ï¸  Found {len(issues)} issue(s)")
        
        if dry_run:
            typer.echo("\n(dry-run mode - no fixes applied)")
        else:
            # Apply fixes
            typer.echo("\nðŸ”§ Applying fixes...\n")
            
            if "config_missing" in issues and not dry_run:
                typer.echo("   Creating default config...")
                config_content = config_manager.create_default_config()
                config_manager.save_config(config_content)
                typer.echo("   âœ“ Config created")
            
            if "weights_missing" in issues and redownload_weights and not dry_run:
                typer.echo("   Downloading weights...")
                from psdfy.weights import get_weights_downloader
                downloader = get_weights_downloader(str(config_manager.weights_dir))
                try:
                    downloader.download_model("sam2", progress_callback=typer.echo)
                    typer.echo("   âœ“ Weights downloaded")
                except Exception as e:
                    typer.echo(f"   âœ— Download failed: {e}", err=True)
            
            if reset_password and not dry_run:
                typer.echo("   Resetting password...")
                config_content = config_manager.create_default_config()
                config_manager.save_config(config_content)
                typer.echo("   âœ“ Password reset to 123456")
            
            if reset_client_secret and not dry_run:
                typer.echo("   Generating new client secret...")
                config = config_manager.load_config()
                import uuid
                config["auth"]["client_secret"] = str(uuid.uuid4())
                typer.echo("   âœ“ Client secret regenerated")
            
            typer.echo("\nâœ… Fixes applied!")

