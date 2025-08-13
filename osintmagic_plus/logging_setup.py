
from __future__ import annotations
import logging, sys, json, os
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass

@dataclass
class LogConfig:
    level: int = logging.INFO
    fmt: str = "human"  # "human" | "json"
    file: str | None = None  # write machine logs to file if set
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3

HUMAN_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"
DATEFMT = "%H:%M:%S"

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def setup_logging(cfg: LogConfig):
    root = logging.getLogger()
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)
    root.setLevel(cfg.level)

    # Console handler (human readable always)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(cfg.level)
    ch.setFormatter(logging.Formatter(HUMAN_FORMAT, datefmt=DATEFMT))
    root.addHandler(ch)

    # Optional machine-readable file
    if cfg.file:
        fh = RotatingFileHandler(cfg.file, maxBytes=cfg.max_bytes, backupCount=cfg.backup_count, encoding="utf-8")
        fh.setLevel(cfg.level)
        if cfg.fmt == "json":
            fh.setFormatter(JsonFormatter())
        else:
            fh.setFormatter(logging.Formatter(HUMAN_FORMAT, datefmt=DATEFMT))
        root.addHandler(fh)

    # Reduce chattiness of noisy libraries
    for noisy in ["aiohttp", "asyncio", "urllib3", "chardet"]:
        logging.getLogger(noisy).setLevel(max(cfg.level, logging.WARNING))
