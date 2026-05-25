"""Update command implementation."""

import typer
import subprocess
import sys
from typing import Optional


def update_command(
    channel: str = "stable",
    dry_run: bool = False,
):
    """
    Update psdfy to the latest version.
    
    Args:
        channel: Release channel (stable or beta)
        dry_run: Show what would be updated
    """
    typer.echo(f"🔄 Checking for updates (channel: {channel})...")
    
    try:
        import requests
    except ImportError:
        typer.echo("requests not installed. Install with: pip install requests", err=True)
        return
    
    # Get current version
    try:
        import psdfy
        current_version = getattr(psdfy, "__version__", "0.1.0")
    except Exception:
        current_version = "0.1.0"
    
    typer.echo(f"Current version: {current_version}")
    
    # Check PyPI for latest version
    try:
        response = requests.get("https://pypi.org/pypi/psdfy/json", timeout=5)
        response.raise_for_status()
        
        pypi_data = response.json()
        latest_version = pypi_data["info"]["version"]
        
        typer.echo(f"Latest version: {latest_version}")
        
        if current_version == latest_version:
            typer.echo("✓ Already up to date!")
            return
        
        typer.echo(f"\n📦 Update available: {current_version} → {latest_version}")
        
        if dry_run:
            typer.echo("(dry-run mode - no changes made)")
            return
        
        # Upgrade via pip
        typer.echo("\n⬆️  Upgrading psdfy...")
        
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--no-deps", "psdfy"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            typer.echo("✓ Upgrade successful!")
            typer.echo("\nNext steps:")
            typer.echo("  1. Restart the service: psdfy stop && psdfy start")
            typer.echo("  2. Check version: psdfy version")
        else:
            typer.echo(f"✗ Upgrade failed: {result.stderr}", err=True)
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            typer.echo("\n⚠️  psdfy is not published to PyPI yet")
            typer.echo("\nTo update from source:")
            typer.echo("  1. Pull latest changes: git pull")
            typer.echo("  2. Reinstall: pip install -e .")
            typer.echo("  3. Restart: psdfy stop && psdfy start")
        else:
            typer.echo(f"✗ Error checking PyPI: {e}", err=True)
    
    except Exception as e:
        typer.echo(f"✗ Error checking for updates: {e}", err=True)

