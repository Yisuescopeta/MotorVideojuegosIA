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
from engine.core.game import Game
from engine.ecs.world import World
from engine.systems.render_system import RenderSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.animation_system import AnimationSystem
from engine.inspector.inspector_system import InspectorSystem
from engine.events.event_bus import EventBus
from engine.events.rule_system import RuleSystem
from engine.scenes.scene_manager import SceneManager
from engine.levels.component_registry import create_default_registry


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
    
    # Crear SceneManager
    scene_manager = SceneManager(registry)
    
    # Cargar escena
    level_data = load_level_data("levels/demo_level.json")
    world = scene_manager.load_scene(level_data)
    
    # Crear bus de eventos y sistema de reglas
    event_bus = EventBus()
    rule_system = RuleSystem(event_bus, world)
    
    # Crear sistemas
    render_system = RenderSystem()
    physics_system = PhysicsSystem(gravity=600)
    collision_system = CollisionSystem(event_bus)
    animation_system = AnimationSystem(event_bus)
    inspector_system = InspectorSystem()
    
    # Configurar juego
    game = Game(
        title="Motor 2D - Fase 12: Escenas",
        width=800,
        height=600,
        target_fps=60
    )
    
    game.set_world(world)
    game.set_scene_manager(scene_manager)
    game.set_render_system(render_system)
    game.set_physics_system(physics_system)
    game.set_collision_system(collision_system)
    game.set_animation_system(animation_system)
    game.set_inspector_system(inspector_system)
    game.set_event_bus(event_bus)
    game.set_rule_system(rule_system)
    
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
    game.run()
    
    print()
    print("Motor finalizado.")


if __name__ == "__main__":
    main()
