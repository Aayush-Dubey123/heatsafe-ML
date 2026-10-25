import logging
import sys
from typing import Optional


def get_ml_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a standardized ML pipeline logger instance.

    Args:
        name (Optional[str]): Name of the ML module requesting logging.
            Defaults to 'heatsafe_ml' when omitted.

    Returns:
        logging.Logger: Configured logger with stream handler and level set.

    Raises:
        None
    """
    logger_name = name or "heatsafe_ml"
    instance = logging.getLogger(logger_name)

    if not instance.handlers:
        instance.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | [ML] %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        instance.addHandler(stream_handler)
        instance.propagate = False

    return instance


# Canonical alias for ML modules
logger = get_ml_logger
