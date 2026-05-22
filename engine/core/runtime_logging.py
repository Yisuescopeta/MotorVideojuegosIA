"""Runtime-safe logging without editor dependencies."""
from typing import List, Tuple

GLOBAL_LOGS: List[Tuple[str, str]] = []

def log_info(msg: str) -> None:
    GLOBAL_LOGS.append(("INFO", msg))

def log_warn(msg: str) -> None:
    GLOBAL_LOGS.append(("WARN", msg))

def log_err(msg: str) -> None:
    GLOBAL_LOGS.append(("ERROR", msg))

def log_debug(msg: str) -> None:
    GLOBAL_LOGS.append(("DEBUG", msg))
