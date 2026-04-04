from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cli.runtime_runner import StandaloneRuntimeRunner


def _default_build_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone packaged player bootstrap")
    parser.add_argument("--build-root", default="", help="Ruta al build exportado. Por defecto usa la carpeta del ejecutable.")
    parser.add_argument("--headless", action="store_true", help="Ejecuta el player en modo headless.")
    parser.add_argument("--frames", type=int, default=0, help="Cantidad de frames para ejecucion headless.")
    parser.add_argument("--seed", type=int, default=None, help="Seed de runtime para ejecucion reproducible.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_root = Path(args.build_root).expanduser().resolve() if args.build_root else _default_build_root()
    return StandaloneRuntimeRunner().run(
        build_root.as_posix(),
        headless=bool(args.headless or args.frames > 0),
        frames=max(0, int(args.frames)),
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
