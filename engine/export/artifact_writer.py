"""Write build artifacts safely."""

from __future__ import annotations

import shutil
from pathlib import Path


def safe_copy(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_dir():
        shutil.rmtree(dst)
    elif dst.exists():
        dst.unlink()
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
