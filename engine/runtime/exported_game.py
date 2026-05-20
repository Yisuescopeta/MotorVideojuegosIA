"""Entry point for exported games.

Usage:
    MyGame.exe                          Normal launch (windowed)
    MyGame.exe --smoke-test             Headless smoke test (60 frames)
    MyGame.exe --headless --frames 3    Headless with N frames
    MyGame.exe --print-runtime-info     Print runtime info and exit

Must NOT import: engine.editor, engine.inspector, tools, tests, docs, main.
Must NOT use EngineAPI in the export path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLCHAIN_UNAVAILABLE_MSG = (
    "TOOLCHAIN/RUNTIME_UNAVAILABLE: raylib not available. "
    "Install pyray for windowed exports: pip install raylib"
)


def main() -> int:
    args = sys.argv[1:]

    from engine.runtime.bootstrap import bootstrap_config

    config = bootstrap_config(args)

    if config.print_runtime_info:
        info = {
            "engine": "MotorVideojuegosIA",
            "frozen": getattr(sys, 'frozen', False),
            "cwd": str(Path.cwd()),
            "entry_scene": config.entry_scene,
            "headless": config.headless,
            "smoke_test": config.smoke_test,
            "project_name": config.project_name,
            "version": config.version,
        }
        print(json.dumps(info, indent=2))
        return 0

    if not config.entry_scene:
        print("ERROR: No entry_scene configured.", file=sys.stderr)
        return 1

    print(f"[Runtime] Starting {config.project_name} v{config.version}")
    print(f"[Runtime] Entry scene: {config.entry_scene}")

    if config.headless:
        return _run_headless_export(config)

    return _run_windowed_export(config)


def _run_headless_export(config) -> int:  # type: ignore[no-untyped-def]
    """Export-only headless runtime. No EngineAPI, no inspector, no editor."""
    from engine.runtime.content_loader import ContentLoader

    loader = ContentLoader(config.base_path)
    manifest_entry = loader.get_entry_scene()
    entry_scene = config.entry_scene or manifest_entry

    scene_data = loader.load_scene_json(entry_scene)
    if scene_data is None:
        print(
            f"ERROR: Entry scene not found: {entry_scene}",
            file=sys.stderr,
        )
        return 1

    from engine.levels.component_registry import create_default_registry
    from engine.scenes.scene import Scene

    registry = create_default_registry()
    scene = Scene(name=entry_scene, data=scene_data, source_path=entry_scene)

    try:
        world = scene.create_world(registry)
    except Exception as exc:
        print(f"ERROR: Cannot build world from scene: {exc}", file=sys.stderr)
        return 1

    from engine.events.event_bus import EventBus
    from engine.systems.collision_system import CollisionSystem
    from engine.systems.physics_system import PhysicsSystem

    event_bus = EventBus()
    physics = PhysicsSystem(gravity=600)
    collision = CollisionSystem(event_bus)

    max_frames = config.max_frames or 3
    print(f"[Runtime] Headless mode: running {max_frames} frames")

    try:
        for _ in range(max_frames):
            physics.update(world, 1.0 / 60.0)
            collision.update(world)

        if config.smoke_test:
            events = event_bus.get_recent_events(50)
            print(
                f"[SmokeTest] OK: {len(events)} events "
                f"in {max_frames} frames"
            )
    except Exception as exc:
        print(f"ERROR during simulation: {exc}", file=sys.stderr)
        return 1

    return 0


def _run_windowed_export(config) -> int:  # type: ignore[no-untyped-def]
    """Attempt windowed export. Fail with TOOLCHAIN_UNAVAILABLE if no display lib."""
    try:
        import pyray  # noqa: F401
    except ImportError:
        try:
            import raylib  # noqa: F401
        except ImportError:
            print(TOOLCHAIN_UNAVAILABLE_MSG, file=sys.stderr)
            return 2

    try:
        return _run_windowed_pyray(config)
    except Exception as exc:
        print(f"ERROR: Windowed export failed: {exc}", file=sys.stderr)
        return 1


def _run_windowed_pyray(config) -> int:  # type: ignore[no-untyped-def]
    """Windowed mode using pyray/raylib."""
    import pyray
    from engine.runtime.content_loader import ContentLoader

    loader = ContentLoader(config.base_path)
    entry_scene = config.entry_scene or loader.get_entry_scene()

    scene_data = loader.load_scene_json(entry_scene)
    if scene_data is None:
        print(
            f"ERROR: Entry scene not found: {entry_scene}",
            file=sys.stderr,
        )
        return 1

    from engine.levels.component_registry import create_default_registry
    from engine.scenes.scene import Scene

    registry = create_default_registry()
    scene = Scene(name=entry_scene, data=scene_data, source_path=entry_scene)

    try:
        world = scene.create_world(registry)
    except Exception as exc:
        print(f"ERROR: Cannot build world from scene: {exc}", file=sys.stderr)
        return 1

    from engine.events.event_bus import EventBus
    from engine.systems.collision_system import CollisionSystem
    from engine.systems.physics_system import PhysicsSystem

    event_bus = EventBus()
    physics = PhysicsSystem(gravity=600)
    collision = CollisionSystem(event_bus)

    window_config = getattr(config, 'window', {}) or {}
    width = int(window_config.get("width", 1280))
    height = int(window_config.get("height", 720))
    title = f"{config.project_name} v{config.version}"

    pyray.init_window(width, height, title.encode() if hasattr(title, 'encode') else title)
    pyray.set_target_fps(60)

    while not pyray.window_should_close():
        physics.update(world, 1.0 / 60.0)
        collision.update(world)

        pyray.begin_drawing()
        pyray.clear_background(pyray.BLACK)
        pyray.end_drawing()

    pyray.close_window()
    return 0


if __name__ == "__main__":
    sys.exit(main())
