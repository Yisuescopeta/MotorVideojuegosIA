from __future__ import annotations

try:
    from pettingzoo import ParallelEnv  # type: ignore
except Exception:
    class ParallelEnv:
        metadata = {}
