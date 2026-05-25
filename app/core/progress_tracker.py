"""Progress tracking utilities for async operations."""

import time
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProgressEvent:
    """Represents a progress event."""
    stage: str
    status: str  # "started", "in_progress", "completed", "failed"
    progress: float = 0.0  # 0-100
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    duration: Optional[float] = None


class AsyncProgressTracker:
    """Track progress of async operations."""
    
    def __init__(self):
        """Initialize progress tracker."""
        self.events: Dict[str, ProgressEvent] = {}
        self.stage_start_times: Dict[str, float] = {}
        self.callbacks: list[Callable[[ProgressEvent], None]] = []
    
    def add_callback(self, callback: Callable[[ProgressEvent], None]):
        """Add a callback to be called on progress events."""
        self.callbacks.append(callback)
    
    def start_stage(self, stage: str, message: str = ""):
        """Mark the start of a stage."""
        self.stage_start_times[stage] = time.time()
        event = ProgressEvent(
            stage=stage,
            status="started",
            progress=0.0,
            message=message or f"Starting {stage}...",
        )
        self.events[stage] = event
        self._emit_event(event)
    
    def update_stage(self, stage: str, progress: float, message: str = ""):
        """Update progress of a stage."""
        event = ProgressEvent(
            stage=stage,
            status="in_progress",
            progress=min(100.0, max(0.0, progress)),
            message=message,
        )
        self.events[stage] = event
        self._emit_event(event)
    
    def complete_stage(self, stage: str, message: str = ""):
        """Mark a stage as completed."""
        duration = None
        if stage in self.stage_start_times:
            duration = time.time() - self.stage_start_times[stage]
        
        event = ProgressEvent(
            stage=stage,
            status="completed",
            progress=100.0,
            message=message or f"Completed {stage}",
            duration=duration,
        )
        self.events[stage] = event
        self._emit_event(event)
    
    def fail_stage(self, stage: str, error: str):
        """Mark a stage as failed."""
        duration = None
        if stage in self.stage_start_times:
            duration = time.time() - self.stage_start_times[stage]
        
        event = ProgressEvent(
            stage=stage,
            status="failed",
            progress=0.0,
            message=f"Failed: {error}",
            duration=duration,
        )
        self.events[stage] = event
        self._emit_event(event)
    
    def get_overall_progress(self) -> float:
        """Get overall progress as percentage."""
        if not self.events:
            return 0.0
        
        completed = sum(1 for e in self.events.values() if e.status == "completed")
        return (completed / len(self.events)) * 100.0
    
    def get_events(self) -> list[ProgressEvent]:
        """Get all progress events."""
        return list(self.events.values())
    
    def _emit_event(self, event: ProgressEvent):
        """Emit event to all callbacks."""
        for callback in self.callbacks:
            try:
                callback(event)
            except Exception:
                pass  # Ignore callback errors


def create_progress_callback(tracker: AsyncProgressTracker, stage: str) -> Callable[[float], None]:
    """Create a progress callback for a stage.
    
    Args:
        tracker: Progress tracker instance
        stage: Stage name
        
    Returns:
        Callback function that accepts progress (0-100)
    """
    def callback(progress: float):
        tracker.update_stage(stage, progress)
    
    return callback
