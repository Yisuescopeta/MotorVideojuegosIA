from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from pettingzoo import ParallelEnv as ParallelEnv
else:
    try:
        from pettingzoo import ParallelEnv as ParallelEnv  # type: ignore
    except Exception:
        class ParallelEnv:
            metadata: ClassVar[dict[str, Any]] = {}
