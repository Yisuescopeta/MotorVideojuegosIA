from __future__ import annotations

from pathlib import Path

from engine.runtime import RuntimeBootstrapError, StandaloneRuntimeLauncher


class StandaloneRuntimeRunner:
    def __init__(self, launcher: StandaloneRuntimeLauncher | None = None) -> None:
        self._launcher = launcher or StandaloneRuntimeLauncher()

    def run(
        self,
        build_root: str,
        *,
        headless: bool = True,
        frames: int = 0,
        seed: int | None = None,
    ) -> int:
        try:
            self._launcher.run(
                Path(build_root),
                headless=headless,
                frames=frames,
                seed=seed,
            )
        except RuntimeBootstrapError as exc:
            print("[ERROR] Standalone runtime bootstrap failed.")
            for diagnostic in exc.diagnostics:
                suffix = f" [{diagnostic.path}]" if diagnostic.path else ""
                print(f" - {diagnostic.code}: {diagnostic.message}{suffix}")
            return 1
        return 0
