from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

from sitecustomize import _install_pyray_stub

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parent.parent.resolve()


def _path_is_repo_root(entry: str) -> bool:
    try:
        candidate = Path(entry or ".").resolve()
    except Exception:
        return False
    return candidate == _REPO_ROOT


def _load_real_pyray() -> bool:
    if os.environ.get("PYRAY_FORCE_STUB", "").lower() in {"1", "true", "yes", "on"}:
        return False
    search_paths = [entry for entry in sys.path if not _path_is_repo_root(entry)]
    spec = importlib.machinery.PathFinder.find_spec("pyray", search_paths)
    if spec is None or spec.loader is None or not getattr(spec, "origin", None):
        return False
    try:
        origin = Path(spec.origin).resolve()
    except Exception:
        return False
    if origin == _THIS_FILE:
        return False

    real_module = importlib.util.module_from_spec(spec)
    sys.modules[__name__] = real_module
    spec.loader.exec_module(real_module)
    globals().update(real_module.__dict__)
    return True


if not _load_real_pyray():
    _install_pyray_stub(force=True)
    globals().update(sys.modules[__name__].__dict__)
