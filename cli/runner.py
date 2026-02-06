"""
cli/runner.py - Gestor de ejecución CLI

PROPÓSITO:
    Coordina la inicialización y ejecución del motor en modo de línea de comandos.
    Parsea argumentos y configura el entorno headless.
"""

import sys
import os
import traceback
from typing import Optional, Any

from cli.headless_game import HeadlessGame
from cli.script_executor import ScriptExecutor

from engine.scenes.scene_manager import SceneManager
from engine.levels.component_registry import create_default_registry
from engine.events.event_bus import EventBus
from engine.events.rule_system import RuleSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.animation_system import AnimationSystem
# Importamos InspectorSystem solo para que no falle la dependencia, 
# aunque en headless no se usa visualmente
from engine.inspector.inspector_system import InspectorSystem
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
        
        # 2. Configurar sistemas
        registry = create_default_registry()
        scene_manager = SceneManager(registry)
        
        event_bus = EventBus() # type: ignore
        physics_system = PhysicsSystem(gravity=600)
        collision_system = CollisionSystem(event_bus)
        animation_system = AnimationSystem(event_bus)
        inspector_system = InspectorSystem()
        selection_system = SelectionSystem()
        
        game.set_scene_manager(scene_manager)
        game.set_physics_system(physics_system)
        game.set_collision_system(collision_system)
        game.set_animation_system(animation_system)
        game.set_inspector_system(inspector_system)
        game.set_event_bus(event_bus)
        game.set_selection_system(selection_system)
        
        # 3. Cargar nivel inicial si se especifica
        if hasattr(args, 'level') and args.level:
            try:
                # Cargar usando scene_manager (espera dict, así que cargamos json primero)
                import json
                with open(args.level, 'r', encoding='utf-8') as f:
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
            game.headless_running = True
            for i in range(args.frames):
                game.step_frame()
                if i % 60 == 0:
                    print(f"Frame {i}/{args.frames}")
            print("[INFO] Finalizado.")
            return
            
        print("[INFO] Modo interactivo no soportado en CLI (usa scripts o --frames).")
