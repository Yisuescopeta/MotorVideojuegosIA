"""
cli/runner.py - Gestor de ejecución CLI

PROPÓSITO:
    Coordina la inicialización y ejecución del motor en modo de línea de comandos.
    Parsea argumentos y configura el entorno headless.
"""

import os
import sys
import traceback
from typing import Any

from cli.headless_game import HeadlessGame
from cli.script_executor import ScriptExecutor
from engine.debug.golden_run import capture_headless_run, compare_golden_runs, load_golden_run, write_golden_run
from engine.events.event_bus import EventBus

# Importamos InspectorSystem solo para que no falle la dependencia,
# aunque en headless no se usa visualmente
from engine.inspector.inspector_system import InspectorSystem
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager
from engine.systems.animation_system import AnimationSystem
from engine.systems.audio_system import AudioSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.input_system import InputSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.render_system import RenderSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem
from engine.systems.selection_system import SelectionSystem


class CLIRunner:
    """
    Gestor principal para la ejecución desde línea de comandos.
    """

    def run(self, args: Any) -> None:
        """
        Ejecuta el motor según los argumentos proporcionados.
        """
        print("=" * 60)
        print("   MOTOR 2D - CLI MODE")
        print("=" * 60)

        # 1. Inicializar Game (Headless)
        game = HeadlessGame()
        project_service = ProjectService(os.getcwd())

        # 2. Configurar sistemas
        registry = create_default_registry()
        scene_manager = SceneManager(registry)

        event_bus = EventBus() # type: ignore
        render_system = RenderSystem()
        physics_system = PhysicsSystem(gravity=600)
        collision_system = CollisionSystem(event_bus)
        animation_system = AnimationSystem(event_bus)
        audio_system = AudioSystem()
        input_system = InputSystem()
        player_controller_system = PlayerControllerSystem()
        script_behaviour_system = ScriptBehaviourSystem()
        inspector_system = InspectorSystem()
        selection_system = SelectionSystem()

        game.set_scene_manager(scene_manager)
        game.set_project_service(project_service)
        game.set_render_system(render_system)
        game.set_physics_system(physics_system)
        game.set_collision_system(collision_system)
        game.set_animation_system(animation_system)
        game.set_audio_system(audio_system)
        game.set_input_system(input_system)
        game.set_player_controller_system(player_controller_system)
        game.set_script_behaviour_system(script_behaviour_system)
        game.set_inspector_system(inspector_system)
        game.set_event_bus(event_bus)
        game.set_selection_system(selection_system)
        render_system.set_debug_options(
            draw_colliders=bool(getattr(args, "debug_colliders", False)),
            draw_labels=bool(getattr(args, "debug_labels", False)),
            draw_tile_chunks=bool(getattr(args, "debug_tile_chunks", False)),
            draw_camera=bool(getattr(args, "debug_camera", False)),
        )
        if getattr(args, "seed", None) is not None:
            game.set_seed(args.seed)

        # 3. Cargar nivel inicial si se especifica
        if hasattr(args, 'level') and args.level:
            try:
                # Cargar usando scene_manager (espera dict, así que cargamos json primero)
                import json
                level_path = project_service.resolve_path(args.level).as_posix() if not os.path.isabs(args.level) else args.level
                with open(level_path, 'r', encoding='utf-8') as f:
                    level_data = json.load(f)
                game.set_world(scene_manager.load_scene(level_data))
            except Exception as e:
                print(f"[ERROR] No se pudo cargar nivel '{args.level}': {e}")
                traceback.print_exc()
                return

        # 4. Ejecutar script si se especifica
        if hasattr(args, 'script') and args.script:
            executor = ScriptExecutor(game)
            try:
                executor.load_script(args.script)
                success = executor.run_all()
                if not success:
                    sys.exit(1)
            except Exception as e:
                print(f"[ERROR] Error ejecutando script: {e}")
                traceback.print_exc()
                sys.exit(1)

            # Si el script termina y tuvo éxito
            print("[INFO] Script finalizado correctamente.")
            return

        # 5. Si no hay script, tal vez solo ejecutar N frames
        if hasattr(args, 'frames') and args.frames > 0:
            print(f"[INFO] Ejecutando {args.frames} frames...")
            if getattr(args, "golden_output", "") or getattr(args, "golden_compare", ""):
                report = capture_headless_run(
                    game,
                    frames=args.frames,
                    capture_every=max(1, int(getattr(args, "capture_every", 1))),
                )
                if getattr(args, "golden_output", ""):
                    write_golden_run(report, args.golden_output)
                    print(f"[INFO] Golden run guardado en: {args.golden_output}")
                if getattr(args, "golden_compare", ""):
                    expected = load_golden_run(args.golden_compare)
                    mismatches = compare_golden_runs(expected, report)
                    if mismatches:
                        print("[ERROR] Golden run mismatch:")
                        for mismatch in mismatches:
                            print(f" - {mismatch}")
                        sys.exit(1)
                    print("[INFO] Golden run coincide con el baseline esperado.")
            else:
                game.headless_running = True
                for i in range(args.frames):
                    game.step_frame()
                    if i % 60 == 0:
                        print(f"Frame {i}/{args.frames}")
            if getattr(args, "debug_dump", "") and game.world is not None and game._render_system is not None:
                dump = game._render_system.get_debug_geometry_dump(game.world, viewport_size=(float(game.width), float(game.height)))
                dump_path = args.debug_dump
                dump_dir = os.path.dirname(dump_path)
                if dump_dir:
                    os.makedirs(dump_dir, exist_ok=True)
                with open(dump_path, "w", encoding="utf-8") as file:
                    json.dump(dump, file, indent=2, ensure_ascii=True)
                print(f"[INFO] Debug dump guardado en: {dump_path}")
            print("[INFO] Finalizado.")
            return

        print("[INFO] Modo interactivo no soportado en CLI (usa scripts o --frames).")
