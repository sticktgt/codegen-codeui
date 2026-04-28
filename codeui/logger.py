from __future__ import annotations

import logging

from codeui.config import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.logging.level.upper(), logging.INFO),
        format=settings.logging.format,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
