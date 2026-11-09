import logging
import sys
from contextvars import ContextVar

# Request correlation ID for the current request; "-" outside of a request.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """
    Logging filter that stamps every record with the active request ID.

    Lets one request be traced across route, controller, CRUD, and service logs.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Attach the current request ID to a log record.

        Never drops records; it only enriches them.

        Args:
            record (logging.LogRecord): Record being emitted.

        Returns:
            bool: Always True so the record is kept.
        """
        record.request_id = request_id_ctx.get()
        return True


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Configure and return a standardized application logger instance.

    Ensures single handler attachment with formatted console output.
    Logs are scoped per module name and carry the request ID.

    Args:
        name (str | None): Module name requesting the logger instance.
            Defaults to 'backend' when omitted.

    Returns:
        logging.Logger: Configured logger with stream handler and level set.
    """
    logger_name = name or "backend"
    instance = logging.getLogger(logger_name)

    if not instance.handlers:
        instance.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.addFilter(RequestIdFilter())
        instance.addHandler(stream_handler)
        instance.propagate = False

    return instance


# Canonical alias expected across all modules
logger = get_logger
