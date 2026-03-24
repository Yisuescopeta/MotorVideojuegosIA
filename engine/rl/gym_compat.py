from __future__ import annotations

import random
from types import SimpleNamespace
from typing import Any

try:
    import gymnasium as gym  # type: ignore
    from gymnasium import spaces  # type: ignore

    GymEnvBase = gym.Env
except Exception:
    class _Discrete:
        def __init__(self, n: int) -> None:
            self.n = int(n)
            self._rng = random.Random()

        def seed(self, seed: int | None = None) -> None:
            self._rng.seed(seed)

        def sample(self) -> int:
            return self._rng.randrange(self.n)

    class _Box:
        def __init__(self, low: Any, high: Any, shape: tuple[int, ...], dtype: Any = float) -> None:
            self.low = low
            self.high = high
            self.shape = shape
            self.dtype = dtype

    class _Dict:
        def __init__(self, spaces_map: dict[str, Any]) -> None:
            self.spaces = dict(spaces_map)

    GymEnvBase = object
    spaces = SimpleNamespace(Discrete=_Discrete, Box=_Box, Dict=_Dict)
