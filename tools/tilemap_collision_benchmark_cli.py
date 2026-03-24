from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.getcwd())

from engine.components.tilemap import Tilemap
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.tilemap.collision_builder import bake_tilemap_colliders


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark de bake de colisiones de tilemap")
    parser.add_argument("--size", type=int, default=128, help="Ancho/alto del grid")
    parser.add_argument("--pattern", type=str, default="border", help="border o full")
    parser.add_argument("--output", type=str, default="", help="Ruta opcional de salida JSON")
    return parser.parse_args()


def build_world(size: int, pattern: str) -> World:
    world = World()
    entity = world.create_entity("Tilemap")
    entity.add_component(Transform(x=0.0, y=0.0, rotation=0.0, scale_x=1.0, scale_y=1.0))
    tiles = []
    for y in range(size):
        for x in range(size):
            is_solid = pattern == "full" or x in {0, size - 1} or y in {0, size - 1}
            if not is_solid:
                continue
            tiles.append({"x": x, "y": y, "tile_id": "wall", "flags": ["solid"]})
    entity.add_component(Tilemap(cell_width=16, cell_height=16, layers=[{"name": "Ground", "tiles": tiles}]))
    return world


def main() -> None:
    args = parse_args()
    world = build_world(max(1, int(args.size)), str(args.pattern))
    report = bake_tilemap_colliders(world, merge_shapes=True)
    report["size"] = int(args.size)
    report["pattern"] = str(args.pattern)
    print(json.dumps(report, indent=2))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
