"""
Compatibility shim for code that imports ``pyray`` while CI installs ``raylib-py``.
"""

from typing import Any

import raylibpy as _raylibpy
from raylibpy import *  # noqa: F401,F403


def __getattr__(name: str) -> Any:
    if hasattr(_raylibpy, name):
        return getattr(_raylibpy, name)
    normalized = name.replace("_2d", "2d").replace("_3d", "3d")
    if hasattr(_raylibpy, normalized):
        return getattr(_raylibpy, normalized)
    raise AttributeError(f"module 'pyray' has no attribute {name!r}")
