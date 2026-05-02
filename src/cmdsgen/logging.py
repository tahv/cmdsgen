from __future__ import annotations

import logging
import logging.config
from logging import Filter
from typing import Final, final, override

from rich.logging import RichHandler

from cmdsgen.utils import clamp, stderr_console


@final
class VerbosityFilter(Filter):
    """Filter based on `-v/-q` flag."""

    def __init__(self, verbosity: int) -> None:
        self.verbosity: Final[int] = clamp(verbosity, 0, 2)

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        if self.verbosity < 1:
            return False
        if self.verbosity == 1:
            return record.levelno >= logging.INFO
        return True


def setup_logging(verbosity: int) -> None:
    """Configure loggers."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "verbosity": {
                    "()": VerbosityFilter,  # ty:ignore[invalid-key]
                    "verbosity": verbosity,  # ty:ignore[invalid-key]
                },  # ty:ignore[missing-typed-dict-key]
            },
            "formatters": {
                "rich": {
                    "datefmt": "[%X]",
                    "format": "%(message)s",
                },
            },
            "handlers": {
                "console": {
                    "filters": ["verbosity"],
                    "formatter": "rich",
                    "()": RichHandler,
                    "console": stderr_console(),
                    "show_time": False,
                    "show_level": True,
                    "show_path": False,
                },
                # TODO(tga): queue handler requires py >= 3.12: https://github.com/python/cpython/issues/93162
            },
            # Configure root logger
            "root": {
                "level": logging.NOTSET,
                "handlers": ["console"],
            },
            # Configure third-party loggers
            "loggers": {
                "aiosqlite": {"level": logging.CRITICAL},
                "aioshttp": {"level": logging.CRITICAL},
                "aiohttp_client_cache": {"level": logging.CRITICAL},
            },
        },
    )
