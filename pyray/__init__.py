from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parent.parent.resolve()
_IS_FROZEN = bool(getattr(sys, "frozen", False))


def _path_is_repo_root(entry: str) -> bool:
    try:
        candidate = Path(entry or ".").resolve()
    except Exception:
        return False
    return candidate == _REPO_ROOT


def _load_real_pyray() -> bool:
    """Try to load the real pyray from site-packages (skipping this shim).

    Returns True if the real module was loaded into sys.modules["pyray"].
    Returns False if we should fall back to the stub.

    In a frozen (PyInstaller) build, raises RuntimeError on failure instead of
    falling back to the no-op stub — a stub would silently suppress all rendering
    (init_window / begin_drawing become no-ops) and console=False hides the problem.
    """
    if os.environ.get("PYRAY_FORCE_STUB", "").lower() in {"1", "true", "yes", "on"}:
        return False

    # In a frozen PyInstaller build the normal "filter out repo root" trick fails:
    # _MEIPASS IS what _REPO_ROOT resolves to, so filtering empties the search list.
    # Use the full sys.path; the origin == _THIS_FILE guard below prevents recursion.
    if _IS_FROZEN:
        search_paths = list(sys.path)
    else:
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


_pyray_loaded_real = _load_real_pyray()

if not _pyray_loaded_real:
    if _IS_FROZEN and not os.environ.get("PYRAY_FORCE_STUB", ""):
        # In a packaged build the real raylib backend MUST be available.
        # Falling back to the no-op stub would silently suppress all rendering:
        # init_window / begin_drawing become no-ops, the window never appears,
        # and with console=False the failure is completely invisible.
        raise RuntimeError(
            "[pyray] Real raylib/pyray backend not found in frozen build.\n"
            "The native CFFI extension (.pyd) was not bundled correctly.\n"
            "Rebuild with the corrected spec: ensure the real pyray (from raylib-py)\n"
            "is resolved via pathex — not the local PROJECT_ROOT/pyray/ stub shim.\n"
            "Hint: put real site-packages BEFORE the project root in pathex.\n"
            "Set PYRAY_FORCE_STUB=1 to override (headless / testing only)."
        )
    from sitecustomize import _install_pyray_stub  # lazy — only needed in non-frozen / test paths
    _install_pyray_stub(force=True)
    globals().update(sys.modules[__name__].__dict__)
