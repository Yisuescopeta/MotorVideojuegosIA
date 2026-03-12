"""
main.py - Motor de Videojuegos 2D

PROPÓSITO:
    Demuestra Scene vs RuntimeWorld (Fase 12).
    
FLUJO:
    EDIT: World editable (desde Scene)
    PLAY: RuntimeWorld (copia) - física activa
    STOP: World restaurado desde Scene

CONTROLES:
    - ESPACIO: Play
    - P: Pause/Resume
    - ESC: Stop (restaura estado original)
    - R: Recargar escena
    - TAB: Inspector
"""

import os
import json
import pyray as rl
from engine.core.game import Game
from engine.ecs.world import World
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
from engine.scenes.scene_manager import SceneManager
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService


from engine.levels.component_registry import create_default_registry
from cli.runner import CLIRunner
from cli.script_executor import ScriptExecutor
import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Motor de Videojuegos 2D")
    parser.add_argument("--headless", action="store_true", help="Ejecutar sin interfaz gráfica")
    parser.add_argument("--script", type=str, help="Ruta al script de automatización")
    parser.add_argument("--frames", type=int, default=0, help="Número de frames a ejecutar")
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


def load_level_data(path: str) -> dict:
    """Carga datos del nivel desde JSON."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main() -> None:
    """Función principal."""
    args = parse_args()
    
    # Modo CLI / Headless (Solo si se pide headless o frames explícitamente)
    # Nota: Si se pasa --script SIN --headless, queremos ver la ejecución visual
    if args.headless or args.frames > 0:
        runner = CLIRunner()
        runner.run(args)
        return

    # Modo GUI Normal
    print("=" * 60)
    print("   MOTOR 2D - Gestión de Escenas (Fase 12)")
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
    project_service = ProjectService(os.getcwd())
    
    # Crear SceneManager
    scene_manager = SceneManager(registry)
    
    # Cargar escena
    level_path = project_service.resolve_path(args.level).as_posix() if not os.path.isabs(args.level) else args.level
    try:
        level_data = load_level_data(level_path)
        world = scene_manager.load_scene(level_data)
    except Exception as e:
        print(f"[ERROR] No se pudo cargar {level_path}: {e}")
        return
    
    # Crear bus de eventos y sistema de reglas
    event_bus = EventBus()
    rule_system = RuleSystem(event_bus, world)
    
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
    
    # Configurar juego
    game = Game(
        title="Motor 2D - Fase 12: Escenas",
        width=800,
        height=600,
        target_fps=60
    )
    
    game.set_world(world)
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
    
    # Configurar ScriptExecutor si se solicitó (Visual Automation)
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
    print("  [ESPACIO] Play  → crea RuntimeWorld (copia)")
    print("  [P]       Pause → congela todo")
    print("  [ESC]     Stop  → restaura World original")
    print("  [R]       Reload")
    print("  [TAB]     Inspector")
    print()
    print("Prueba:")
    print("  1. ESPACIO → entidades caen")
    print("  2. ESC → entidades vuelven a posición original")
    print("-" * 60)
    
    # Ejecutar
    rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE | rl.FLAG_VSYNC_HINT)
    game.run()
    
    print()
    print("Motor finalizado.")


if __name__ == "__main__":
    main()
