"""Compact application logging configuration."""

import logging
from pathlib import Path


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("boutiqaat")
    if logger.handlers:
        return logger
    Path("logs").mkdir(exist_ok=True)
    handler = logging.FileHandler("logs/app.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
