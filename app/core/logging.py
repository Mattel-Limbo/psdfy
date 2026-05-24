"""Structured logging configuration."""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add request_id if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
) -> logging.Logger:
    """
    Setup structured logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format for logs
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger("psdfy")
    logger.setLevel(getattr(logging, level))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level))
    
    # Set formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


class RequestLogger:
    """Helper for logging with request_id."""
    
    def __init__(self, logger: logging.Logger):
        """Initialize request logger."""
        self.logger = logger
    
    def log_request_start(
        self,
        request_id: str,
        method: str,
        path: str,
        **extra,
    ):
        """Log request start."""
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(request)",
            0,
            f"Request started: {method} {path}",
            (),
            None,
        )
        record.request_id = request_id
        record.extra = {"method": method, "path": path, **extra}
        self.logger.handle(record)
    
    def log_request_end(
        self,
        request_id: str,
        status_code: int,
        duration_ms: float,
        **extra,
    ):
        """Log request end."""
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(request)",
            0,
            f"Request completed: {status_code} ({duration_ms:.1f}ms)",
            (),
            None,
        )
        record.request_id = request_id
        record.extra = {"status_code": status_code, "duration_ms": duration_ms, **extra}
        self.logger.handle(record)
    
    def log_stage(
        self,
        request_id: str,
        stage: str,
        duration_ms: float,
        **extra,
    ):
        """Log pipeline stage."""
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "(stage)",
            0,
            f"Stage completed: {stage} ({duration_ms:.1f}ms)",
            (),
            None,
        )
        record.request_id = request_id
        record.extra = {"stage": stage, "duration_ms": duration_ms, **extra}
        self.logger.handle(record)
    
    def log_error(
        self,
        request_id: str,
        error: str,
        **extra,
    ):
        """Log error."""
        record = self.logger.makeRecord(
            self.logger.name,
            logging.ERROR,
            "(error)",
            0,
            f"Error: {error}",
            (),
            None,
        )
        record.request_id = request_id
        record.extra = extra
        self.logger.handle(record)


# Global logger instance
_logger = None
_request_logger = None


def get_logger() -> logging.Logger:
    """Get or create logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


def get_request_logger() -> RequestLogger:
    """Get or create request logger instance."""
    global _request_logger
    if _request_logger is None:
        _request_logger = RequestLogger(get_logger())
    return _request_logger
