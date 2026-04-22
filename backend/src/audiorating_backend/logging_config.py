
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .settings import settings

def setup_logging():
    """Configure application-wide logging.

    Returns:
        None: This function configures the global logging system in place.
    """
    logging.basicConfig(
        format='%(levelname)s: %(name)s: %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def get_admin_audit_logger() -> logging.Logger:
    """Return a dedicated logger for persistent admin audit events."""
    logger_name = "audiorating.admin_audit"
    audit_logger = logging.getLogger(logger_name)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False

    if audit_logger.handlers:
        return audit_logger

    log_path = Path(settings.admin_audit_log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=settings.admin_audit_log_max_bytes,
        backupCount=settings.admin_audit_log_backup_count,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)

    return audit_logger
