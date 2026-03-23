from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.getcwd())

from engine.components.renderorder2d import RenderOrder2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.systems.render_system import RenderSystem


def build_synthetic_world(sprite_count: int, texture_path: str) -> World:
    world = World()
    world.feature_metadata = {
        "render_2d": {
            "sorting_layers": ["Default", "Gameplay", "Foreground"],
        }
    }
    for index in range(sprite_count):
        entity = world.create_entity(f"BenchSprite_{index}")
        entity.add_component(Transform(x=float(index % 250), y=float(index // 250), rotation=0.0, scale_x=1.0, scale_y=1.0))
        entity.add_component(Sprite(texture_path=texture_path, width=32, height=32))
        entity.add_component(RenderOrder2D(sorting_layer="Gameplay", order_in_layer=0, render_pass="World"))
    return world


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark headless del render graph 2D.")
    parser.add_argument("--sprite-count", type=int, default=5000, help="Numero de sprites sinteticos a perfilar.")
    parser.add_argument("--texture-path", default="assets/bench_shared.png", help="Texture path logico usado por los sprites sinteticos.")
    parser.add_argument("--output", default="", help="Ruta opcional del JSON de salida.")
    args = parser.parse_args()

    world = build_synthetic_world(max(1, int(args.sprite_count)), args.texture_path)
    render_system = RenderSystem()
    report = {
        "scene": "synthetic_render_benchmark",
        "sprite_count": int(args.sprite_count),
        "texture_path": args.texture_path,
        "metrics": render_system.profile_world(world),
    }

    payload = json.dumps(report, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
