import logging
import os
from rich.logging import RichHandler

# Target Defination
SYSTEM_LOG_FILE = "/var/log/sentinel.log"
FALLBACK_LOG_FILE = "/tmp/sentinel-user.log"

def _setup_logger() -> logging.Logger:
    """Configures a dual-handler logger (Rich CLI + Secure File)."""

    # Base logger
    sentinel_logger = logging.getLogger("sentinel_core")
    sentinel_logger.setLevel(logging.INFO)

    if sentinel_logger.handlers:
        return sentinel_logger
    
    # Determining where we can write (Root vs User space)
    is_root = os.geteuid() == 0
    log_path = SYSTEM_LOG_FILE if is_root else FALLBACK_LOG_FILE

    # The Secure File Handler
    try:
        if not os.path.exists(log_path):
            with open(log_path, 'a') as f:
                pass
        
        # SECURITY: Lock down /var/log/sentinel.log to root-only
        if is_root:
            os.chmod(log_path, 0o600)
        
        file_handler = logging.FileHandler(log_path)

        # Stricter, parsable timestamps in the file (No Rich formatting)
        file_formatter = logging.Formatter(
            fmt = "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        sentinel_logger.addHandler(file_handler)
    
    except PermissionError:
        pass

    # Setup of Rich Console Handler
    rich_handler = RichHandler(
        rich_tracebacks=True,
        show_time=False,
        show_path=False
    )
    rich_handler.setLevel(logging.INFO)
    sentinel_logger.addHandler(rich_handler)

    return sentinel_logger

logger = _setup_logger()