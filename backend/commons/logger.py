import logging
import os
import sys
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a standardized application logger instance.

    Ensures single handler attachment with formatted console output.
    Logs are scoped per module name to guarantee traceable diagnostics.

    Args:
        name (Optional[str]): Module name requesting the logger instance.
            Defaults to 'backend' when omitted.

    Returns:
        logging.Logger: Configured logger with stream handler and level set.

    Raises:
        None
    """
    logger_name = name or "backend"
    instance = logging.getLogger(logger_name)

    if not instance.handlers:
        instance.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        instance.addHandler(stream_handler)
        instance.propagate = False

    return instance


# Canonical alias expected across all modules
logger = get_logger
