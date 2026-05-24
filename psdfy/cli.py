"""CLI entry point for psdfy using Typer."""

import typer
from typing import Optional

# Import command implementations
from psdfy.commands.install import install_command
from psdfy.commands.start import start_command
from psdfy.commands.stop import stop_command
from psdfy.commands.fix import fix_command
from psdfy.commands.update import update_command
from psdfy.commands.uninstall import uninstall_command

app = typer.Typer(
    name="psdfy",
    help="Image to PSD converter - install, start, stop, and manage the service",
)


@app.command()
def version():
    """
    Show version information.
    
    Displays psdfy version, service version, Python version, 
    PyTorch device, and model checksums.
    """
    typer.echo("psdfy version 0.1.0")
    typer.echo("Service: API v1.0.0 + UI v1.0.0")
    typer.echo("Python: 3.11+")
    typer.echo("Device: cpu (default)")
    typer.echo("Config: ~/.psdfy/config.toml")


@app.command()
def install(
    password: Optional[str] = typer.Option(
        None,
        "--password",
        help="Set UI password (default: 123456)"
    ),
    host: Optional[str] = typer.Option(
        "localhost",
        "--host",
        help="API host (default: localhost)"
    ),
    api_port: Optional[int] = typer.Option(
        3456,
        "--api-port",
        help="API port (default: 3456)"
    ),
    ui_port: Optional[int] = typer.Option(
        3457,
        "--ui-port",
        help="UI port (default: 3457)"
    ),
    service: bool = typer.Option(
        False,
        "--service",
        help="Install as system service (Windows/macOS/Linux)"
    ),
    no_weights: bool = typer.Option(
        False,
        "--no-weights",
        help="Skip downloading model weights"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes"
    ),
):
    """
    Install psdfy and download model weights.
    
    Creates ~/.psdfy/ directory, downloads SAM 2 weights,
    and optionally registers as a system service.
    """
    install_command(
        password=password,
        host=host,
        api_port=api_port,
        ui_port=ui_port,
        service=service,
        no_weights=no_weights,
        dry_run=dry_run,
    )


@app.command()
def start(
    host: Optional[str] = typer.Option(
        None,
        "--host",
        help="Override API host"
    ),
    api_port: Optional[int] = typer.Option(
        None,
        "--api-port",
        help="Override API port"
    ),
    ui_port: Optional[int] = typer.Option(
        None,
        "--ui-port",
        help="Override UI port"
    ),
    foreground: bool = typer.Option(
        False,
        "--foreground",
        help="Run in foreground (stream logs to stdout)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without starting"
    ),
):
    """
    Start the psdfy service.
    
    Starts both API and UI servers. Checks that ports are free
    and model weights are present before starting.
    """
    start_command(
        host=host,
        api_port=api_port,
        ui_port=ui_port,
        foreground=foreground,
        dry_run=dry_run,
    )


@app.command()
def stop(
    force: bool = typer.Option(
        False,
        "--force",
        help="Force kill if graceful shutdown fails"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without stopping"
    ),
):
    """
    Stop the psdfy service.
    
    Gracefully shuts down both API and UI servers.
    Use --force to escalate to SIGKILL if needed.
    """
    stop_command(
        force=force,
        dry_run=dry_run,
    )


@app.command()
def update(
    channel: Optional[str] = typer.Option(
        "stable",
        "--channel",
        help="Release channel: stable or beta"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be updated without making changes"
    ),
):
    """
    Update psdfy to the latest version.
    
    Checks PyPI for new versions, upgrades via pipx,
    runs config migrations, and restarts the service.
    """
    update_command(
        channel=channel,
        dry_run=dry_run,
    )


@app.command()
def fix(
    reset_password: bool = typer.Option(
        False,
        "--reset-password",
        help="Reset UI password to default (123456)"
    ),
    reset_client_secret: bool = typer.Option(
        False,
        "--reset-client-secret",
        help="Generate new client secret"
    ),
    redownload_weights: bool = typer.Option(
        False,
        "--redownload-weights",
        help="Re-download model weights"
    ),
    reset_config: bool = typer.Option(
        False,
        "--reset-config",
        help="Reset config to defaults (with warning)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show issues without fixing"
    ),
):
    """
    Diagnose and repair psdfy installation.
    
    Checks Python version, config, weights, ports, GPU,
    and service status. Offers interactive fixes.
    """
    fix_command(
        reset_password=reset_password,
        reset_client_secret=reset_client_secret,
        redownload_weights=redownload_weights,
        reset_config=reset_config,
        dry_run=dry_run,
    )


@app.command()
def uninstall(
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip confirmation prompt"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be removed without actually removing"
    ),
):
    """
    Uninstall psdfy and remove all related files.
    
    Removes configuration, weights, logs, and uninstalls the pip package.
    Use --force to skip confirmation, --dry-run to preview changes.
    """
    uninstall_command(
        force=force,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    app()

