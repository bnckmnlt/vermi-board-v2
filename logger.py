import logging
from colorama import Fore, Style, init

init(autoreset=True)

class ColorFormatter(logging.Formatter):
    COLOR_MAP = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT
    }

    def format(self, record):
        level_color = self.COLOR_MAP.get(record.levelno, "")
        levelname = f"{level_color}{record.levelname}{Style.RESET_ALL}"
        original_levelname = record.levelname
        record.levelname = f"{level_color}{original_levelname:<6}{Style.RESET_ALL}"

        formatted = super().format(record)
        record.levelname = original_levelname
        return formatted

def setup_logger():
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter(
        fmt="{asctime} - {levelname:6s} - {message}",
        datefmt="[%Y-%m-%d] %H:%M:%S",
        style="{"
    ))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [handler]
