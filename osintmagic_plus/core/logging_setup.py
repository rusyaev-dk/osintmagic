import logging
from rich.logging import RichHandler

def setup_logging(level: str = "info"):
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_time=True, show_level=True)]
    )
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
