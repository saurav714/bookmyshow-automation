
from logging import StreamHandler

from loguru import logger as _logger
from loguru._logger import Logger as _Logger

LOGGER_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "  + \
    "<level>{level: <8}</level> | "  + \
    "<cyan>{extra[name]: <8}</cyan> - <level>{message}</level>"


def _init_logging(debug: bool=False) -> None:
    _logger.remove()
    _logger.add(StreamHandler(), format=LOGGER_FORMAT, colorize=True, level="DEBUG" if debug else "INFO")


def get_logger(name: str) -> _Logger:
    return _logger.bind(name=name)
