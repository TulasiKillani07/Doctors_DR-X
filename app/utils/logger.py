"""
DRX Doctor Platform — Logging Utility

Production-ready logging with:
- Rotating file logs (10MB per file, 10 backups)
- Console output for development
- Prevents duplicate handlers
- Platform-specific log directory

Usage:
    from app.utils.logger import get_drx_logger

    logger = get_drx_logger(__name__)
    logger.info("Doctor logged in")
    logger.error("MRX connection failed", exc_info=True)
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
import platform


def get_log_directory() -> Path:
    """Get log directory from environment or use platform-specific default."""
    if log_dir_env := os.getenv("LOG_DIR"):
        return Path(log_dir_env)

    system = platform.system()
    if system == "Windows":
        return Path("C:/Logs/DRX_Platform")
    elif system == "Linux":
        try:
            if os.geteuid() == 0:
                return Path("/var/log/drx_platform")
        except AttributeError:
            pass
        return Path.home() / ".drx_platform" / "logs"
    elif system == "Darwin":
        return Path.home() / ".drx_platform" / "logs"
    else:
        return Path.home() / ".drx_platform" / "logs"


def get_drx_logger(
    module_name: str = __name__,
    console_level: Optional[str] = None,
    file_level: Optional[str] = None
) -> logging.Logger:
    """
    Get or create a configured logger for DRX Doctor Platform.

    Args:
        module_name: Name of the module (usually __name__)
        console_level: Override console log level
        file_level: Override file log level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(module_name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    default_level = os.getenv("LOG_LEVEL", "INFO").upper()
    console_level = (console_level or default_level).upper()
    file_level = (file_level or default_level).upper()

    log_dir = get_log_directory()

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "drx_platform_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "drx.log"

    fmt_string = (
        "[%(levelname)s] %(asctime)s | %(name)s | "
        "%(filename)s:%(lineno)d (%(funcName)s) | "
        "%(message)s"
    )
    formatter = logging.Formatter(fmt=fmt_string, datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(getattr(logging, console_level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (rotating)
    try:
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding="utf-8",
            delay=True
        )
        file_handler.setLevel(getattr(logging, file_level))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        logger.warning("Could not create file handler. Logging to console only.")

    logger.propagate = False
    return logger
