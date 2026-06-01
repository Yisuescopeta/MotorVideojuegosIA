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
    from engine.runtime.shared_game_runtime import SharedGameRuntime

    loader = ContentLoader(config.base_path)

    if config.smoke_test:
        integrity = loader.verify_integrity()
        if not integrity["valid"]:
            tampered = integrity["tampered"]
            print(
                f"ERROR: Content integrity check FAILED: "
                f"{len(tampered)} entries tampered/missing",
                file=sys.stderr,
            )
            for entry in tampered[:10]:
                print(f"  - {entry}", file=sys.stderr)
            return 3

    manifest_entry = loader.get_entry_scene()
    entry_scene = config.entry_scene or manifest_entry

    from engine.levels.component_registry import create_default_registry

    registry = create_default_registry()
    runtime = SharedGameRuntime(
        loader=loader,
        registry=registry,
        window_config=getattr(config, 'window', {}),
    )
    runtime.setup_scripts_path()

    if not runtime.load_scene(entry_scene):
        print(
            f"ERROR: Entry scene not found: {entry_scene}",
            file=sys.stderr,
        )
        return 1

    max_frames = config.max_frames or 3
    print(f"[Runtime] Headless mode: running {max_frames} frames")

    try:
        for _ in range(max_frames):
            runtime.run_frame(1.0 / 60.0)

        if config.smoke_test:
            events = runtime.get_recent_events(50)
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
        import traceback

        traceback.print_exc()
        print(f"ERROR: Windowed export failed: {exc}", file=sys.stderr)
        return 1


def _draw_loading_screen(
    pyray: Any,
    width: float,
    height: float,
    project_name: str,
    status: str = "Loading...",
    progress: float = 0.0,
) -> None:
    bar_width = min(400.0, width * 0.6)
    bar_height = 18.0
    bar_x = (width - bar_width) / 2.0
    bar_y = height / 2.0 + 20.0

    pyray.begin_drawing()
    pyray.clear_background(pyray.BLACK)

    title = f"{project_name}"
    title_size = 36
    title_width = pyray.measure_text(title, title_size)
    pyray.draw_text(
        title,
        int((width - title_width) / 2.0),
        int(height / 2.0 - 60.0),
        title_size,
        pyray.WHITE,
    )

    status_size = 16
    status_width = pyray.measure_text(status, status_size)
    pyray.draw_text(
        status,
        int((width - status_width) / 2.0),
        int(height / 2.0 - 10.0),
        status_size,
        pyray.GRAY,
    )

    if progress > 0.0:
        pyray.draw_rectangle(int(bar_x), int(bar_y), int(bar_width), int(bar_height), pyray.DARKGRAY)
        filled = int(bar_width * min(progress, 1.0))
        if filled > 0:
            pyray.draw_rectangle(int(bar_x), int(bar_y), filled, int(bar_height), pyray.SKYBLUE)
        pyray.draw_rectangle_lines(int(bar_x), int(bar_y), int(bar_width), int(bar_height), pyray.GRAY)

    pyray.end_drawing()


def _run_windowed_pyray(config) -> int:  # type: ignore[no-untyped-def]
    """Windowed mode using pyray/raylib."""
    import pyray
    from engine.runtime.content_loader import ContentLoader
    from engine.runtime.shared_game_runtime import SharedGameRuntime

    loader = ContentLoader(config.base_path)
    entry_scene = config.entry_scene or loader.get_entry_scene()

    from engine.levels.component_registry import create_default_registry

    registry = create_default_registry()
    window_config = getattr(config, 'window', {}) or {}
    width = int(window_config.get("width", 1280))
    height = int(window_config.get("height", 720))
    title = f"{config.project_name} v{config.version}"

    pyray.init_window(width, height, title)
    if hasattr(pyray, "is_window_ready") and not pyray.is_window_ready():
        print("ERROR: raylib window was not created", file=sys.stderr)
        if hasattr(pyray, "close_window"):
            pyray.close_window()
        return 2

    _draw_loading_screen(pyray, width, height, config.project_name, "Loading scene...")

    runtime = SharedGameRuntime(
        loader=loader,
        registry=registry,
        window_config=window_config,
    )
    runtime.setup_scripts_path()

    if not runtime.load_scene(entry_scene, enter_play=False):
        print(
            f"ERROR: Entry scene not found: {entry_scene}",
            file=sys.stderr,
        )
        if hasattr(pyray, "close_window"):
            pyray.close_window()
        return 1

    world = runtime.world
    preloader = runtime.resource_preloader_system if runtime.systems is not None else None
    plan = preloader.build_preload_plan(world) if preloader is not None and world is not None else []
    total = len(plan)

    if total > 0 and preloader is not None:
        runtime.play_runtime(preload_resources=False)
        runtime_world = runtime.world
        if runtime_world is not None:
            chunk_size = max(1, total // 30)
            loaded = 0
            while loaded < total:
                batch = min(chunk_size, total - loaded)
                count, _resolved = preloader.preload_budgeted(runtime_world, batch)
                loaded += count
                progress = loaded / total
                status = f"Precargando assets... ({loaded}/{total})"
                _draw_loading_screen(pyray, width, height, config.project_name, status, progress)
    else:
        runtime.play_runtime(preload_resources=True)

    try:
        pyray.set_target_fps(60)

        while not pyray.window_should_close():
            viewport = (float(width), float(height))
            mouse = pyray.get_mouse_position()
            pointer_state = {
                "x": float(mouse.x),
                "y": float(mouse.y),
                "down": bool(pyray.is_mouse_button_down(pyray.MOUSE_BUTTON_LEFT)),
                "pressed": bool(pyray.is_mouse_button_pressed(pyray.MOUSE_BUTTON_LEFT)),
                "released": bool(pyray.is_mouse_button_released(pyray.MOUSE_BUTTON_LEFT)),
            }
            runtime.run_frame(1.0 / 60.0, pointer_state=pointer_state)

            pyray.begin_drawing()
            pyray.clear_background(pyray.BLACK)

            if runtime.world is not None:
                runtime.render(viewport)

            pyray.end_drawing()
    finally:
        if hasattr(pyray, "close_window"):
            pyray.close_window()
    return 0


if __name__ == "__main__":
    sys.exit(main())
