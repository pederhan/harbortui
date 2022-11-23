from loguru import logger

from .config import HarborTUIConfig
from .dirs import LOGS_DIR as LOGS_DIR  # explicit re-export

LOG_FILE = LOGS_DIR / "harbortui.log"
STRUCTLOG_FILE = LOGS_DIR / "harbortui.structlog"


LOGGING_INIT = False


def init_logging(config: HarborTUIConfig) -> None:
    global LOGGING_INIT
    if LOGGING_INIT:
        return

    try:
        _do_init_logging(config)
    except Exception as e:
        print(f"Failed to initialize logging: {e}")
        return
    else:
        LOGGING_INIT = True


def _do_init_logging(config: HarborTUIConfig) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger.remove()
    if config.logging.enabled:
        logger.add(LOG_FILE, level=config.logging.level.value)
    if config.logging.structlog:
        logger.add(
            # "structlog.stdlib.ProcessorFormatter.wrap_for_formatter",
            # processor=structlog.dev.ConsoleRenderer(colors=False),
            STRUCTLOG_FILE,
            level=config.logging.level.value,
        )
