import logging
import sys


LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-32s | %(filename)s:%(lineno)d | %(message)s"
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


def short_value(value, head=4, tail=4):
    if value is None:
        return "-"

    text = str(value)

    if text.isdigit() and len(text) >= 8:
        return f"{text[:2]}...{text[-2:]}"

    limit = head + tail + 3

    if len(text) <= limit:
        return text

    return f"{text[:head]}...{text[-tail:]}"
