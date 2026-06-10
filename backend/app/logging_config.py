"""Structured logging configuration for the FastAPI application."""

import logging.config
import sys
from typing import Any

import structlog


def setup_logging(json_format: bool = False, log_level: str = "INFO") -> None:
    """Configure structlog to intercept and format all app and third-party logs."""
    # Clear any existing root handlers to avoid duplicate log outputs
    logging.root.handlers = []

    # Processor chain shared between structlog wrappers and standard logs
    shared_processors: list[Any] = [
        # Merges request context variables bound via structlog.contextvars
        structlog.contextvars.merge_contextvars,
        # Adds the logger name to the record
        structlog.stdlib.add_logger_name,
        # Adds the log level (e.g., INFO, WARNING, ERROR)
        structlog.stdlib.add_log_level,
        # Enables extra attributes logging
        structlog.stdlib.ExtraAdder(),
        # Timestamps formatted in ISO 8601 UTC format
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Formats stack trace if present
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Converts byte values to unicode strings
        structlog.processors.UnicodeDecoder(),
    ]

    # Render format selection
    if json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            # Prepares events for the Python standard library logger formatter
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Setup the logging config dict for Uvicorn and stdlib loggers redirection
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog_formatter": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": renderer,
                "foreign_pre_chain": shared_processors,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structlog_formatter",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "fastapi": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": log_level,
        },
    }

    logging.config.dictConfig(logging_config)
