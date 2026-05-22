"""CLI entry point for psdfy."""

import click


@click.group()
@click.version_option()
def app():
    """PSD layer converter and processor."""
    pass


@app.command()
def convert():
    """Convert PSD file to layers."""
    click.echo("Convert command - stub implementation")


@app.command()
def process():
    """Process PSD layers."""
    click.echo("Process command - stub implementation")


if __name__ == "__main__":
    app()
