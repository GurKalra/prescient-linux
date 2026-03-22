import logging
import os

# Target Defination
SYSTEM_LOG_FILE = "/var/log/prescient.log"
FALLBACK_LOG_FILE = "/tmp/prescient-user.log"

def _setup_logger() -> logging.Logger:
    """Configures a secure, background-only file logger."""

    # Base logger
    prescient_logger = logging.getLogger("prescient_core")
    prescient_logger.setLevel(logging.INFO)

    if prescient_logger.handlers:
        return prescient_logger
    
    # Determining where we can write (Root vs User space)
    is_root = os.geteuid() == 0
    log_path = SYSTEM_LOG_FILE if is_root else FALLBACK_LOG_FILE

    # The Secure File Handler
    try:
        if not os.path.exists(log_path):
            with open(log_path, 'a') as f:
                pass
        
        # Enforcing 644 so that standard users (TUI) read it .
        if is_root:
            os.chmod(log_path, 0o644)
        
        file_handler = logging.FileHandler(log_path)

        # Stricter, parsable timestamps in the file (No Rich formatting)
        file_formatter = logging.Formatter(
            fmt = "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        prescient_logger.addHandler(file_handler)
    
    except PermissionError:
        pass

    return prescient_logger

logger = _setup_logger()