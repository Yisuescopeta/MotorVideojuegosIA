"""
main.py - Motor de Videojuegos 2D

PROPOSITO:
    Demuestra Scene vs RuntimeWorld (Fase 12).

FLUJO:
    EDIT: World editable (desde Scene)
    PLAY: RuntimeWorld (copia) - fisica activa
    STOP: World restaurado desde Scene

CONTROLES:
    - Botones superiores: Play, Pause, Stop, Reload
    - TAB: Inspector
"""

import os
import pyray as rl
from engine.core.game import Game
from engine.systems.render_system import RenderSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.animation_system import AnimationSystem
from engine.systems.audio_system import AudioSystem
from engine.systems.input_system import InputSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem
from engine.inspector.inspector_system import InspectorSystem
from engine.events.event_bus import EventBus
from engine.events.rule_system import RuleSystem
from engine.systems.selection_system import SelectionSystem
from engine.systems.ui_render_system import UIRenderSystem
from engine.systems.ui_system import UISystem
from engine.scenes.scene_manager import SceneManager
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.api import EngineAPI


from engine.levels.component_registry import create_default_registry
from cli.runner import CLIRunner
from cli.script_executor import ScriptExecutor
import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Motor de Videojuegos 2D")
    parser.add_argument("--headless", action="store_true", help="Ejecutar sin interfaz grafica")
    parser.add_argument("--script", type=str, help="Ruta al script de automatizacion")
    parser.add_argument("--frames", type=int, default=0, help="Numero de frames a ejecutar")
    parser.add_argument("--level", type=str, default="levels/demo_level.json", help="Ruta al nivel a cargar")
    return parser.parse_args()


def ensure_sprite_sheet() -> None:
    """Genera el sprite sheet si no existe."""
    if os.path.exists("assets/test_spritesheet.png"):
        return
    try:
        import tools.generate_test_spritesheet as gen
        gen.generate_spritesheet_raylib()
    except Exception as e:
        print(f"[WARNING] Sprite sheet: {e}")
def main() -> None:
    """Funcion principal."""
    args = parse_args()

    # Modo CLI / Headless (Solo si se pide headless o frames explicitamente)
    # Nota: Si se pasa --script SIN --headless, queremos ver la ejecucion visual
    if args.headless or args.frames > 0:
        runner = CLIRunner()
        runner.run(args)
        return

    # Modo GUI Normal
    print("=" * 60)
    print("   MOTOR 2D - Gestion de Escenas (Fase 12)")
    print("=" * 60)
    print()
    print("Scene vs RuntimeWorld:")
    print("  - EDIT usa World desde Scene (editable)")
    print("  - PLAY usa RuntimeWorld (copia temporal)")
    print("  - STOP restaura World desde Scene")
    print()

    ensure_sprite_sheet()

    # Crear registro de componentes
    registry = create_default_registry()
    project_service = ProjectService(os.getcwd(), auto_ensure=False)

    # Crear SceneManager
    scene_manager = SceneManager(registry)

    # Crear bus de eventos y sistema de reglas
    event_bus = EventBus()
    rule_system = RuleSystem(event_bus, None)

    # Crear sistemas
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
    ui_system = UISystem()
    ui_render_system = UIRenderSystem()

    # Configurar juego
    game = Game(
        title="Motor 2D - Fase 12: Escenas",
        width=800,
        height=600,
        target_fps=60,
    )

    game.set_project_service(project_service)
    game.set_scene_manager(scene_manager)
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
    game.set_rule_system(rule_system)
    game.set_rule_system(rule_system)
    game.set_selection_system(selection_system)
    game.set_ui_system(ui_system)
    game.set_ui_render_system(ui_render_system)

    assistant_api = EngineAPI(project_root=project_service.project_root.as_posix())
    assistant_api.attach_runtime(game, scene_manager, project_service)
    game.set_assistant_api(assistant_api)

    # Configurar ScriptExecutor si se solicito (Visual Automation)
    if args.script:
        print(f"[INFO] Cargando script visual: {args.script}")
        executor = ScriptExecutor(game)
        try:
            executor.load_script(args.script)
            game.set_script_executor(executor)
        except Exception as e:
            print(f"[ERROR] Fallo al cargar script: {e}")
            return

    print()
    print("Controles:")
    print("  Botones superiores -> Play / Pause / Stop / Reload")
    print("  [TAB]     Inspector")
    print()
    print("Prueba:")
    print("  1. Selecciona o crea un proyecto desde el launcher inicial")
    print("  2. Abre una escena del proyecto y usa los botones superiores para iniciar y pausar")
    print("-" * 60)

    # Ejecutar
    rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE | rl.FLAG_VSYNC_HINT)
    game.run()

    print()
    print("Motor finalizado.")


if __name__ == "__main__":
    main()
