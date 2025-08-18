from __future__ import annotations

import logging
import os

_configured = False

def configure_logging(level: str | int | None = None) -> None:
    """Configure root logging once.

    Priority: explicit arg > TAXPROTEST_LOG_LEVEL > DEBUG if TAXPROTEST_ENV=dev > INFO.
    Safe no-op if already configured.
    """
    global _configured
    if _configured:
        return
    env_level = os.getenv("TAXPROTEST_LOG_LEVEL")
    if level is None:
        if env_level:
            level = env_level
        elif os.getenv("TAXPROTEST_ENV", "").lower() == "dev":
            level = "DEBUG"
        else:
            level = "INFO"
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _configured = True

def get_logger(name: str | None = None) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name if name else "taxprotest")
