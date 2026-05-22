"""Bootstrap the exported game runtime."""

from __future__ import annotations

import sys
from pathlib import Path

from engine.runtime.runtime_config import RuntimeConfig


def find_runtime_config(exe_dir: Path) -> Path | None:
    candidates = [
        exe_dir / "runtime_config.json",
        exe_dir.parent / "runtime_config.json",
        Path.cwd() / "runtime_config.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def bootstrap_config(args: list[str] | None = None) -> RuntimeConfig:
    if getattr(sys, 'frozen', False):
        # PyInstaller extracts datas to sys._MEIPASS at runtime
        meipass = Path(getattr(sys, '_MEIPASS', sys.executable))
        exe_dir = Path(sys.executable).parent
        config_path = find_runtime_config(meipass)
        config = RuntimeConfig.from_file(config_path) if config_path else RuntimeConfig()
        config.base_path = meipass
    else:
        exe_dir = Path.cwd()
        config_path = find_runtime_config(exe_dir)
        config = RuntimeConfig.from_file(config_path) if config_path else RuntimeConfig()
        config.base_path = exe_dir
    if args:
        config.apply_cli_flags(args)
    return config
