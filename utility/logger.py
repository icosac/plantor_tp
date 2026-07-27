import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path
import re

try:
    from loguru import logger as _loguru_logger
except Exception:
    _loguru_logger = None


ITALIC = "\033[3m"
BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[91m"
FILE_NAME_WIDTH = 30


def bold(text):
    """Return text in bold."""
    return f"{BOLD}{text}{RESET}"


def italic(text):
    """Return text in italic."""
    return f"{ITALIC}{text}{RESET}"


LEVEL_NAME_MAP = {
    "DEBUG": "DBG",
    "INFO": "INF",
    "WARNING": "WRN",
    "ERROR": "ERR",
    "CRITICAL": "CRT",
}

ANGULAR_BRACKETS_PATTERN = re.compile(r"\<.*?\>", re.DOTALL)
CURLY_BRACKETS_PATTERN = re.compile(r"\{.*?\}", re.DOTALL)


def _short_level_name(level_name):
    short_name = LEVEL_NAME_MAP.get(level_name, level_name)
    if short_name in {"ERR", "CRT"}:
        return f"{RED}{short_name}{RESET}"
    return short_name


def _format_time(record_time):
    return record_time.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


def _escape_braces(text):
    # Escape braces for Loguru formatting and angle brackets for markup safety.
    
    match = ANGULAR_BRACKETS_PATTERN.search(text)
    if match:
        text = text.replace("<", "\\<").replace(">", "\\>")

    match = CURLY_BRACKETS_PATTERN.search(text)
    if match:
        text = text.replace("{", "{{").replace("}", "}}")

    return text


def _format_console(record):
    level = _short_level_name(record["level"].name)
    message = _escape_braces(record["message"])
    return f"[{BOLD}{level}{RESET}] {message}\n"


def _format_file(record):
    time_str = _format_time(record["time"])
    level = _short_level_name(record["level"].name)
    message = _escape_braces(record["message"])
    file_name = f"{record['file'].name:<{FILE_NAME_WIDTH}}"
    return f"{time_str} {ITALIC}{file_name}{RESET} [{BOLD}{level}{RESET}] {message}\n"


class ShortLevelFormatter(logging.Formatter):
    def format(self, record):
        original_levelname = record.levelname
        record.levelname = _short_level_name(original_levelname)
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


class Logger(logging.Logger):
    def __init__(self, name, output_dir=".", output_file_name="log.log"):
        assert os.path.exists(output_dir), f"{output_dir} does not exist, create it first"
        super().__init__(name)
        self._use_loguru = _loguru_logger is not None
        self._output_dir = output_dir
        self._output_file_name = output_file_name
        self._max_bytes = 200 * 1024 
        self._loguru_sinks = []
        super().setLevel(logging.DEBUG)

        if self._use_loguru:
            self._loguru = _loguru_logger.bind(logger_name=name)
            self._configure_loguru()
        else:
            # Create handlers
            self.c_handler = logging.StreamHandler()
            self.f_handler = RotatingFileHandler(
                os.path.join(output_dir, output_file_name),
                maxBytes=self._max_bytes,
                backupCount=1,
            )
            self.c_handler.setLevel(self.level)
            self.f_handler.setLevel(self.level)
            # Create formatters and add them to handlers
            self.c_format = ShortLevelFormatter(f"[{BOLD}%(levelname)s{RESET}] %(message)s")
            self.f_format = ShortLevelFormatter(
                f"%(asctime)s {ITALIC}%(filename)s{RESET} [{BOLD}%(levelname)s{RESET}] %(message)s"
            )
            self.c_handler.setFormatter(self.c_format)
            self.f_handler.setFormatter(self.f_format)
            # Add handlers to the logger
            self.addHandler(self.c_handler)
            self.addHandler(self.f_handler)

    def _configure_loguru(self):
        # Remove default and previously-added sinks to enforce our formatting.
        self._loguru.remove()
        self._loguru_sinks = []
        level_name = logging.getLevelName(self.level)
        self._loguru_sinks.append(
            self._loguru.add(
                sys.stderr,
                level=level_name,
                format=_format_console,
                colorize=False,
                backtrace=False,
                diagnose=False,
            )
        )
        self._loguru_sinks.append(
            self._loguru.add(
                os.path.join(self._output_dir, self._output_file_name),
                level=level_name,
                format=_format_file,
                rotation=self._max_bytes,
                retention=1,
                colorize=False,
                backtrace=False,
                diagnose=False,
            )
        )

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        if self._use_loguru:
            level_name = logging.getLevelName(level)
            if args:
                msg = msg % args
                args = ()
            depth = 2 + max(stacklevel - 1, 0)
            self._loguru.opt(depth=depth, exception=exc_info).log(level_name, msg, *args)
            return
        super()._log(level, msg, args, exc_info=exc_info, extra=extra, stack_info=stack_info, stacklevel=stacklevel)

    def setLevel(self, level):
        super().setLevel(level)
        if self._use_loguru:
            self._configure_loguru()
        else:
            for handler in self.handlers:
                handler.setLevel(level)

    def set_debug(self):
        """Set the logger to debug mode."""
        self.setLevel(logging.DEBUG)
        
    def set_info(self):
        """Set the logger to info mode."""
        self.setLevel(logging.INFO)

    def set_warning(self):
        """Set the logger to warning mode."""
        self.setLevel(logging.WARNING)

    def set_error(self):
        """Set the logger to error mode."""
        self.setLevel(logging.ERROR)

    def set_critical(self):
        """Set the logger to critical mode."""
        self.setLevel(logging.CRITICAL)

    def change_output_dir_file(self, output_dir, output_file):
        self._output_dir = output_dir
        self._output_file_name = output_file
        if self._use_loguru:
            self._configure_loguru()
        else:
            new_handler = RotatingFileHandler(
                os.path.join(output_dir, output_file),
                maxBytes=self._max_bytes,
                backupCount=1,
            )
            new_handler.setLevel(self.f_handler.level)
            new_handler.setFormatter(self.f_format)
            self.removeHandler(self.f_handler)
            self.f_handler = new_handler
            self.addHandler(self.f_handler)


logger = Logger(str(Path(__file__).parent).split("/")[-1])
