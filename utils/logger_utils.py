"""日志配置（colorlog 彩色输出）。"""
import logging

import colorlog

_handler = colorlog.StreamHandler()
_handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
))


def configure_project_logging(level=logging.DEBUG):
    root = logging.getLogger()
    root.setLevel(level)
    if not any(isinstance(h, colorlog.StreamHandler) for h in root.handlers):
        root.addHandler(_handler)


configure_project_logging()
logger = logging.getLogger("market-research-agent")
