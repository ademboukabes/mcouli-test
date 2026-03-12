import logging


DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


logger = logging.getLogger("multAI")


def configure_logger(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format=DEFAULT_LOG_FORMAT,
        force=True,
    )
