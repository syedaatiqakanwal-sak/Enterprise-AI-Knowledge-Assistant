import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.config import settings

# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Formatting
FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)

def get_console_handler():
    """Setup console logging with optional colors."""
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    return console_handler

def get_file_handler():
    """Setup rotating file logging."""
    file_handler = RotatingFileHandler(
        LOGS_DIR / "app.log", 
        maxBytes=10485760, # 10MB
        backupCount=5
    )
    file_handler.setFormatter(FORMATTER)
    return file_handler

def setup_logging():
    """Initialize enterprise logging."""
    logger = logging.getLogger()
    
    # Set logging level based on environment
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logger.setLevel(log_level)
    
    # Add handlers
    logger.addHandler(get_console_handler())
    logger.addHandler(get_file_handler())
    
    # Disable propagation for some noisy libraries
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.error").handlers = []
    
    logger.info(f"Logging initialized in {settings.ENVIRONMENT} mode")

# Call this in main.py
