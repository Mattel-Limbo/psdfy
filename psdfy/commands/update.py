"""Update command implementation."""

import subprocess
import sys
from typing import Optional
from psdfy import __version__
from psdfy.progress_utils import (
    print_status,
    print_success,
    print_error,
    print_warning,
    print_loading,
)


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
    print_loading(f"Checking for updates (channel: {channel})...")
    
    try:
        import requests
    except ImportError:
        print_error("requests not installed. Install with: pip install requests")
        return
    
    # Get current version
    try:
        import psdfy
        current_version = getattr(psdfy, "__version__", __version__)
    except Exception:
        current_version = __version__
    
    print_status("📦", f"Current version: {current_version}")
    
    # Check PyPI for latest version
    try:
        response = requests.get("https://pypi.org/pypi/psdfy/json", timeout=5)
        response.raise_for_status()
        
        pypi_data = response.json()
        latest_version = pypi_data["info"]["version"]
        
        print_status("📦", f"Latest version: {latest_version}")
        
        if current_version == latest_version:
            print_success("Already up to date!")
            return
        
        print_status("📦", f"Update available: {current_version} → {latest_version}")
        
        if dry_run:
            print_status("ℹ️", "(dry-run mode - no changes made)")
            return
        
        # Upgrade via pip
        print_loading("Upgrading psdfy...")
        
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--no-deps", "psdfy"],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            print_success("Upgrade successful!")
            print_status("ℹ️", "Next steps:")
            print_status("  ", "1. Restart the service: psdfy stop && psdfy start")
            print_status("  ", "2. Check version: psdfy version")
        else:
            print_error(f"Upgrade failed: {result.stderr}")
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print_warning("psdfy is not published to PyPI yet")
            print_status("ℹ️", "To update from source:")
            print_status("  ", "1. Pull latest changes: git pull")
            print_status("  ", "2. Reinstall: pip install -e .")
            print_status("  ", "3. Restart: psdfy stop && psdfy start")
        else:
            print_error(f"Error checking PyPI: {e}")
    
    except Exception as e:
        print_error(f"Error checking for updates: {e}")
