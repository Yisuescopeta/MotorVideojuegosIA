"""Pure file picker model — no pyray, no windowing, no rendering."""
from __future__ import annotations

import fnmatch
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileEntry:
    """Entrada individual en el file picker."""
    name: str
    path: str
    is_dir: bool
    extension: str = ""
    size: int = 0


@dataclass
class FilePickerModel:
    """Modelo puro de selección de archivos/directorios."""
    root_path: str = "."
    current_path: str = "."
    entries: list[FileEntry] = field(default_factory=list)
    selected_path: str | None = None
    filter_pattern: str = "*"
    show_hidden: bool = False
    title: str = "Select File"
    mode: str = "open"
    filename_input: str = ""
    schema_version: int = 1
    _scroll_offset: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        if self.entries:
            return
        self._refresh()

    def navigate_to(self, path: str) -> bool:
        target = self._resolve(path)
        if not target.is_dir():
            return False
        self.current_path = str(target.resolve())
        self._refresh()
        return True

    def go_up(self) -> bool:
        current = Path(self.current_path).resolve()
        root = Path(self.root_path).resolve()
        if current == root or current.parent == current:
            return False
        parent = current.parent
        try:
            parent.relative_to(root)
        except ValueError:
            return False
        self.current_path = str(parent)
        self._refresh()
        return True

    def set_filter(self, pattern: str) -> None:
        self.filter_pattern = pattern

    def select(self, path: str) -> None:
        self.selected_path = path

    def filtered_entries(self) -> list[FileEntry]:
        entries = self.entries
        if not self.show_hidden:
            entries = [e for e in entries if not e.name.startswith(".")]
        if self.mode == "directory":
            return [e for e in entries if e.is_dir]
        pattern = self.filter_pattern or "*"
        result: list[FileEntry] = []
        for e in entries:
            if e.is_dir:
                result.append(e)
            elif fnmatch.fnmatch(e.name, pattern):
                result.append(e)
        return result

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FilePickerModel":
        payload: dict[str, Any] = dict(data)
        payload["entries"] = [FileEntry(**dict(e)) for e in payload.get("entries", [])]
        return cls(**payload)

    def _refresh(self) -> None:
        p = Path(self.current_path)
        if not p.is_dir():
            self.entries = []
            return
        entries: list[FileEntry] = []
        try:
            for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                entry = FileEntry(
                    name=item.name,
                    path=str(item.resolve()),
                    is_dir=item.is_dir(),
                    extension=item.suffix if not item.is_dir() else "",
                    size=item.stat().st_size if not item.is_dir() else 0,
                )
                entries.append(entry)
        except (OSError, PermissionError):
            pass
        self.entries = entries

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return (Path(self.current_path) / p).resolve()
