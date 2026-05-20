"""Runtime configuration for exported games."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RuntimeConfig:
    def __init__(self, data: dict[str, Any] | None = None):
        d = data or {}
        self.schema_version: int = int(d.get("schema_version", 1))
        self.entry_scene: str = str(d.get("entry_scene", ""))
        self.project_name: str = str(d.get("project_name", ""))
        self.version: str = str(d.get("version", "0.1.0"))
        self.window: dict[str, Any] = dict(d.get("window", {}))
        self.debug_tools: bool = bool(d.get("debug_tools", False))
        self.headless: bool = False
        self.smoke_test: bool = False
        self.max_frames: int = 0
        self.print_runtime_info: bool = False
        self.base_path: Path = Path.cwd()

    @classmethod
    def from_file(cls, path: str | Path) -> "RuntimeConfig":
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        config = cls(data)
        config.base_path = p.parent.resolve()
        return config

    def apply_cli_flags(self, args: list[str]) -> None:
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--smoke-test":
                self.smoke_test = True
                self.headless = True
                if self.max_frames == 0:
                    self.max_frames = 60
            elif arg == "--headless":
                self.headless = True
                if i + 2 < len(args) and args[i + 1] == "--frames":
                    try:
                        self.max_frames = int(args[i + 2])
                        i += 2
                    except (IndexError, ValueError):
                        self.max_frames = 3
                elif self.max_frames == 0:
                    self.max_frames = 3
            elif arg == "--print-runtime-info":
                self.print_runtime_info = True
            i += 1
