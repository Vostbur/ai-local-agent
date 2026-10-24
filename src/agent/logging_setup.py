import logging
from pathlib import Path


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Configure and return the 'agent' logger.

    Creates the logs directory if it does not exist.
    Uses a file handler (UTF-8, append mode) and a console handler.
    Repeated calls do not add duplicate handlers.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("agent")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        logs_dir / "agent.log", encoding="utf-8", mode="a"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
