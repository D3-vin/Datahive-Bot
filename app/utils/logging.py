"""
Simple logging for Datahive
"""

import sys
from pathlib import Path
from typing import Optional

from colorama import init, Fore, Style
from loguru import logger

init(autoreset=True)


class DatahiveLogger:
    """Simple logger for Datahive"""
    
    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Setup simple logging"""
        logger.remove()
        
        # Console with colors
        logger.add(
            sys.stdout,
            colorize=True,
            format="<light-cyan>{time:HH:mm:ss}</light-cyan> | <level>{level: <8}</level> | - <white>{message}</white>",
            level=self.log_level
        )
        
        # Ensure logs directory
        Path("./logs").mkdir(exist_ok=True)
        
        # File logging
        logger.add(
            "./logs/datahive.log",
            rotation="1 day",
            retention="7 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            level=self.log_level
        )
    
    def _format_account(self, account: str) -> str:
        """Format account for display"""
        return account
    
    def info(self, message: str, account: Optional[str] = None) -> None:
        """Log info message"""
        if account:
            formatted_account = self._format_account(account)
            logger.info(f"[{formatted_account}] {message}")
        else:
            logger.info(message)
    
    def success(self, message: str, account: Optional[str] = None) -> None:
        """Log success message"""
        if account:
            formatted_account = self._format_account(account)
            logger.success(f"[{formatted_account}] {message}")
        else:
            logger.success(message)
    
    def warning(self, message: str, account: Optional[str] = None) -> None:
        """Log warning message"""
        if account:
            formatted_account = self._format_account(account)
            logger.warning(f"[{formatted_account}] {message}")
        else:
            logger.warning(message)
    
    def error(self, message: str, account: Optional[str] = None) -> None:
        """Log error message"""
        if account:
            formatted_account = self._format_account(account)
            logger.error(f"[{formatted_account}] {message}")
        else:
            logger.error(message)
    
    def debug(self, message: str, account: Optional[str] = None) -> None:
        """Log debug message"""
        if account:
            formatted_account = self._format_account(account)
            logger.debug(f"[{formatted_account}] {message}")
        else:
            logger.debug(message)


# Global logger
_logger_instance: Optional[DatahiveLogger] = None


def get_logger() -> DatahiveLogger:
    """Get global logger instance"""
    global _logger_instance
    if _logger_instance is None:
        try:
            from app.config.settings import get_settings
            settings = get_settings()
            log_level = settings.logging_level
        except Exception:
            log_level = "INFO"
        
        _logger_instance = DatahiveLogger(log_level)
    return _logger_instance


def init_logger(level: str) -> DatahiveLogger:
    """Initialize logger with specific level"""
    global _logger_instance
    _logger_instance = DatahiveLogger(level)
    return _logger_instance