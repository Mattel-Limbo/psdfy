"""Progress bar utilities with emoji support for CLI operations."""

from typing import Optional, Callable, Any
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
)
from rich.console import Console

console = Console()


class ProgressBar:
    """Wrapper for rich Progress with emoji support."""

    def __init__(self, emoji: str = "⏳"):
        """Initialize progress bar with emoji.
        
        Args:
            emoji: Emoji to display with progress bar
        """
        self.emoji = emoji
        self.progress = None

    def __enter__(self):
        """Context manager entry."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn(f"{self.emoji} [progress.description]{{task.description}}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        )
        self.progress.__enter__()
        return self.progress

    def __exit__(self, *args):
        """Context manager exit."""
        if self.progress:
            self.progress.__exit__(*args)


class DownloadProgress:
    """Wrapper for download progress with emoji support."""

    def __init__(self, emoji: str = "📥"):
        """Initialize download progress with emoji.
        
        Args:
            emoji: Emoji to display with download progress
        """
        self.emoji = emoji
        self.progress = None

    def __enter__(self):
        """Context manager entry."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn(f"{self.emoji} [progress.description]{{task.description}}"),
            DownloadColumn(),
            BarColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        )
        self.progress.__enter__()
        return self.progress

    def __exit__(self, *args):
        """Context manager exit."""
        if self.progress:
            self.progress.__exit__(*args)


def print_status(emoji: str, message: str, status: str = ""):
    """Print status message with emoji.
    
    Args:
        emoji: Emoji to display
        message: Main message
        status: Optional status suffix
    """
    if status:
        console.print(f"{emoji} {message} {status}")
    else:
        console.print(f"{emoji} {message}")


def print_success(message: str):
    """Print success message with checkmark emoji."""
    print_status("✅", message)


def print_error(message: str):
    """Print error message with X emoji."""
    print_status("❌", message)


def print_warning(message: str):
    """Print warning message with warning emoji."""
    print_status("⚠️", message)


def print_info(message: str):
    """Print info message with info emoji."""
    print_status("ℹ️", message)


def print_loading(message: str):
    """Print loading message with rocket emoji."""
    print_status("🚀", message)


def create_progress_task(
    progress: Progress,
    description: str,
    total: Optional[float] = None,
    emoji: str = "⏳",
) -> int:
    """Create a progress task with emoji in description.
    
    Args:
        progress: Progress instance
        description: Task description
        total: Total steps (None for indeterminate)
        emoji: Emoji to prepend to description
        
    Returns:
        Task ID
    """
    full_description = f"{emoji} {description}"
    return progress.add_task(full_description, total=total)


def with_progress(
    description: str,
    emoji: str = "⏳",
    total: Optional[float] = None,
) -> Callable:
    """Decorator for functions that should show progress.
    
    Args:
        description: Progress description
        emoji: Emoji to display
        total: Total steps (None for indeterminate)
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            with ProgressBar(emoji) as progress:
                task_id = create_progress_task(
                    progress, description, total=total, emoji=""
                )
                try:
                    result = func(progress, task_id, *args, **kwargs)
                    progress.update(task_id, completed=total or 100)
                    return result
                except Exception as e:
                    print_error(f"Error during {description}: {str(e)}")
                    raise
        return wrapper
    return decorator
