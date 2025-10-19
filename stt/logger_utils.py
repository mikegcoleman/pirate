#!/usr/bin/env python3
"""
Structured JSON Logging Utilities for Mr. Bones Pirate Assistant

Provides unified logging infrastructure for centralized collection in Grafana Loki.

Features:
- JSON-formatted logs with consistent schema
- Request ID (reqId) generation and propagation
- Context-aware logging (inherits reqId in threads/async tasks)
- Rotating file handler + stdout mirror
- Configurable log levels and stack trace inclusion
"""

import json
import logging
import os
import sys
import traceback
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

# Context variable for request ID propagation across threads/async tasks
_request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

# Environment configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
LOG_FILE = os.getenv("LOG_FILE", "/var/log/mr-bones/client.log")
LOG_STACK = os.getenv("LOG_STACK", "0") == "1"
REQUEST_ID_HEADER = os.getenv("REQUEST_ID_HEADER", "X-Request-Id")

# Log levels mapping
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs JSON log entries."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as a JSON string.

        Schema:
        {
          "ts": "2025-10-19T18:01:23.456Z",
          "level": "info",
          "reqId": "27077ed3",
          "msg": "TTS generation completed",
          "meta": { "chunk": "2/3", "duration_ms": 404 }
        }
        """
        # Get timestamp in UTC ISO-8601 with milliseconds and Z suffix
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        # Normalize level name to lowercase
        level = record.levelname.lower()
        if level == "warning":
            level = "warn"

        # Extract reqId from context or record
        req_id = getattr(record, 'reqId', None) or _request_id_context.get()

        # Build base log entry
        log_entry = {
            "ts": timestamp,
            "level": level,
            "reqId": req_id,
            "msg": record.getMessage()
        }

        # Add metadata if present
        meta = getattr(record, 'meta', {})

        # Add stack trace to meta if this is an error and LOG_STACK is enabled
        if record.exc_info and LOG_STACK:
            meta['stack'] = ''.join(traceback.format_exception(*record.exc_info))
        elif record.levelno >= logging.ERROR and LOG_STACK and not record.exc_info:
            # Capture current stack if error but no exception info
            meta['stack'] = ''.join(traceback.format_stack())

        # Only include meta if it has content
        if meta:
            log_entry["meta"] = meta

        return json.dumps(log_entry, ensure_ascii=False)


class StructuredLogger:
    """
    Structured logger that outputs JSON with request ID correlation.

    Usage:
        from logger_utils import get_logger, set_request_id

        logger = get_logger()

        # Start of conversation turn
        req_id = generate_request_id()
        set_request_id(req_id)

        logger.info("Starting conversation turn", duration_ms=123)
        logger.error("API call failed", error="Connection timeout", status_code=503)
    """

    def __init__(self, name: str = "mr-bones"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(LOG_LEVELS.get(LOG_LEVEL, logging.INFO))
        self.logger.propagate = False

        # Remove any existing handlers
        self.logger.handlers = []

        # JSON formatter
        formatter = JSONFormatter()

        # Stdout handler (always enabled)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        self.logger.addHandler(stdout_handler)

        # File handler with rotation (if LOG_FILE is set)
        if LOG_FILE:
            try:
                # Ensure log directory exists
                log_dir = os.path.dirname(LOG_FILE)
                if log_dir:
                    os.makedirs(log_dir, exist_ok=True)

                # Rotating file handler: 5MB per file, keep 5 backups
                file_handler = RotatingFileHandler(
                    LOG_FILE,
                    maxBytes=5_000_000,  # 5 MB
                    backupCount=5,
                    encoding='utf-8'
                )
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                # Log to stdout if file handler setup fails
                self._log_internal("warn", f"Failed to create file handler: {e}")

    def _log_internal(self, level: str, msg: str, **meta):
        """Internal logging method that bypasses structured formatting for bootstrap messages."""
        print(f"[{level.upper()}] {msg}", file=sys.stderr if level == "error" else sys.stdout)

    def _log(self, level: str, msg: str, req_id: Optional[str] = None, **meta):
        """
        Internal log method.

        Args:
            level: Log level (debug, info, warn, error)
            msg: Log message
            req_id: Optional request ID (overrides context)
            **meta: Additional metadata as kwargs
        """
        log_level = LOG_LEVELS.get(level.upper(), logging.INFO)

        # Create log record with metadata
        extra = {
            'meta': meta if meta else {}
        }

        # Add reqId if provided (overrides context)
        if req_id:
            extra['reqId'] = req_id

        self.logger.log(log_level, msg, extra=extra)

    def debug(self, msg: str, req_id: Optional[str] = None, **meta):
        """Log debug message."""
        self._log("debug", msg, req_id, **meta)

    def info(self, msg: str, req_id: Optional[str] = None, **meta):
        """Log info message."""
        self._log("info", msg, req_id, **meta)

    def warn(self, msg: str, req_id: Optional[str] = None, **meta):
        """Log warning message."""
        self._log("warn", msg, req_id, **meta)

    def error(self, msg: str, req_id: Optional[str] = None, exc_info: bool = False, **meta):
        """
        Log error message.

        Args:
            msg: Error message
            req_id: Optional request ID
            exc_info: Include exception traceback if True
            **meta: Additional metadata
        """
        log_level = logging.ERROR
        extra = {
            'meta': meta if meta else {}
        }
        if req_id:
            extra['reqId'] = req_id

        self.logger.log(log_level, msg, extra=extra, exc_info=exc_info)


# Global logger instance
_logger_instance: Optional[StructuredLogger] = None


def get_logger(name: str = "mr-bones") -> StructuredLogger:
    """
    Get or create the global structured logger instance.

    Args:
        name: Logger name (default: "mr-bones")

    Returns:
        StructuredLogger instance
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = StructuredLogger(name)
    return _logger_instance


def generate_request_id() -> str:
    """
    Generate a new request ID (8-char lowercase hex from UUID v4).

    Returns:
        8-character request ID (e.g., "27077ed3")
    """
    return uuid.uuid4().hex[:8]


def generate_operation_id() -> str:
    """
    Generate an operation ID for background tasks (8-char lowercase hex).

    Returns:
        8-character operation ID (e.g., "a3f9c812")
    """
    return uuid.uuid4().hex[:8]


def set_request_id(req_id: str):
    """
    Set the request ID in the current context.

    This reqId will be inherited by all logs in the current thread/async task
    and any child threads/tasks spawned from it.

    Args:
        req_id: Request ID to set
    """
    _request_id_context.set(req_id)


def get_request_id() -> Optional[str]:
    """
    Get the current request ID from context.

    Returns:
        Current request ID or None if not set
    """
    return _request_id_context.get()


def clear_request_id():
    """Clear the request ID from the current context."""
    _request_id_context.set(None)


def add_request_id_header(headers: Dict[str, str], req_id: Optional[str] = None) -> Dict[str, str]:
    """
    Add request ID header to outbound HTTP request headers.

    Args:
        headers: Existing headers dict
        req_id: Request ID (uses context if not provided)

    Returns:
        Updated headers dict with X-Request-Id header
    """
    request_id = req_id or get_request_id()
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    return headers


def extract_request_id_from_headers(headers: Dict[str, str]) -> Optional[str]:
    """
    Extract request ID from HTTP response headers (case-insensitive).

    Args:
        headers: HTTP response headers dict

    Returns:
        Request ID if found, None otherwise
    """
    # Case-insensitive header lookup
    for key, value in headers.items():
        if key.lower() == REQUEST_ID_HEADER.lower():
            return value
    return None
