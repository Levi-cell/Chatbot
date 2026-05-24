import logging
import sys


LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-32s | %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(level=logging.INFO):
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
    )


def short_value(value, head=14, tail=8):
    if value is None:
        return "-"

    text = str(value)
    limit = head + tail + 3

    if len(text) <= limit:
        return text

    return f"{text[:head]}...{text[-tail:]}"
