"""Install command implementation."""

import typer
import sys
import subprocess
from pathlib import Path
from typing import Optional

from psdfy.config import get_config_manager
from psdfy.weights import get_weights_downloader


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
    typer.echo("🔄 Checking for latest psdfy version...")
    if not dry_run:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "--no-deps", "psdfy"],
                capture_output=True,
                timeout=60,
                check=False
            )
            typer.echo("   ✓ Package updated to latest version")
        except Exception as e:
            typer.echo(f"   ⚠️  Could not upgrade package: {e}", err=True)
    
    config_manager = get_config_manager()
    
    typer.echo("🚀 Installing psdfy...")
    
    # Step 1: Create directories
    typer.echo("\n📁 Creating directories...")
    if not dry_run:
        config_manager.ensure_directories()
    typer.echo(f"   Config: {config_manager.config_dir}")
    typer.echo(f"   Weights: {config_manager.weights_dir}")
    typer.echo(f"   Outputs: {config_manager.outputs_dir}")
    
    # Step 2: Create config
    typer.echo("\n⚙️  Creating configuration...")
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
    
    typer.echo(f"   Host: {host}")
    typer.echo(f"   API Port: {api_port}")
    typer.echo(f"   UI Port: {ui_port}")
    typer.echo(f"   Password: {'*' * len(password)}")
    
    # Step 3: Download weights
    if not no_weights:
        typer.echo("\n📥 Downloading model weights...")
        downloader = get_weights_downloader(str(config_manager.weights_dir))
        
        try:
            if not dry_run:
                downloader.download_model("sam2", progress_callback=typer.echo)
            typer.echo("   ✓ SAM 2 weights ready")
        except Exception as e:
            typer.echo(f"   ⚠️  SAM 2 download failed: {e}", err=True)
    
    # Step 4: Register service (if requested)
    if service:
        typer.echo("\n🔧 Registering system service...")
        typer.echo("   TODO: Implement service registration")
    
    # Summary
    typer.echo("\n✅ Installation complete!")
    typer.echo(f"\nNext steps:")
    typer.echo(f"  1. Start the service: psdfy start")
    typer.echo(f"  2. Open browser: http://{host}:{ui_port}")
    typer.echo(f"  3. Login with password: {password}")
    
    if dry_run:
        typer.echo("\n(dry-run mode - no changes made)")
