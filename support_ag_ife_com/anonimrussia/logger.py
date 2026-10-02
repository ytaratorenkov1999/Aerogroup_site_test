import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Callable

from django.conf import settings


class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[37m",     # серый
        "INFO": "\033[32m",      # зелёный
        "WARNING": "\033[33m",   # желтый
        "ERROR": "\033[31m",     # красный
        "CRITICAL": "\033[41m",  # красный фон
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


class CrewLogger:


    LOG_DIR = os.path.join(getattr(settings, "BASE_DIR", "."), "logs")
    LOG_FILE = os.path.join(LOG_DIR, "anonimrussia_crew.log")

    LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    CONSOLE_LEVEL = logging.INFO
    FILE_LEVEL = logging.DEBUG
    MAX_BYTES = 5 * 1024 * 1024
    BACKUP_COUNT = 5

    _loggers = {}

    @classmethod
    def get_logger(cls, name: str = "anonimrussia") -> logging.Logger:
        """Возвращает настроенный логгер, повторно используя уже собранный."""
        if name in cls._loggers:
            return cls._loggers[name]

        os.makedirs(cls.LOG_DIR, exist_ok=True)

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        logger.addHandler(cls._build_console_handler())
        logger.addHandler(cls._build_file_handler())

        cls._loggers[name] = logger
        return logger

    @classmethod
    def _build_console_handler(cls) -> logging.StreamHandler:
        handler = logging.StreamHandler()
        handler.setLevel(cls.CONSOLE_LEVEL)
        handler.setFormatter(ColorFormatter(cls.LOG_FORMAT, datefmt=cls.DATE_FORMAT))
        return handler

    @classmethod
    def _build_file_handler(cls) -> RotatingFileHandler:
        handler = RotatingFileHandler(
            cls.LOG_FILE,
            maxBytes=cls.MAX_BYTES,
            backupCount=cls.BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setLevel(cls.FILE_LEVEL)
        handler.setFormatter(logging.Formatter(cls.LOG_FORMAT, datefmt=cls.DATE_FORMAT))
        return handler


class StreamCaptureHandler(logging.Handler):

    def __init__(self, logger: logging.Logger, callback: Callable[[str], None], level=logging.INFO):
        super().__init__(level=level)
        self.setFormatter(logging.Formatter(
            CrewLogger.LOG_FORMAT, datefmt=CrewLogger.DATE_FORMAT
        ))
        self._logger = logger
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(self.format(record))
        except Exception:
            self.handleError(record)

    def __enter__(self) -> "StreamCaptureHandler":
        self._logger.addHandler(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._logger.removeHandler(self)