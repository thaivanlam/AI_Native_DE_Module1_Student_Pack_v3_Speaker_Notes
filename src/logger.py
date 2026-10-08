import logging

from src.config import SETTINGS

LOG_DIR = SETTINGS.root / "logs"
LOG_FILE = LOG_DIR / "pipeline.log"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: str = "pipeline"):
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(LOG_FORMAT)

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger
