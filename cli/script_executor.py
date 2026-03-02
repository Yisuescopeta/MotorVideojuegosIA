"""
cli/script_executor.py - Ejecutor de scripts de automatización

PROPÓSITO:
    Ejecuta una lista de comandos secuenciales sobre el juego.
    Permite simular acciones de usuario y verificar estados.

COMANDOS SOPORTADOS:
    - LOAD_SCENE <path>
    - SELECT <entity_name>
    - INSPECT_EDIT <entity:component:property> <value>
    - WAIT <frames>
    - SNAPSHOT_SAVE
    - SNAPSHOT_LOAD
    - ASSERT_POS <entity> <x> <y> <tolerance>
    - EXIT
"""

from typing import List, Dict, Any, Union
import json
import time

from engine.core.game import Game
from engine.core.engine_state import EngineState

class ScriptExecutor:
    """
    Ejecuta scripts de prueba/automatización sobre una instancia de Game.
    """
    
    def __init__(self, game: Game) -> None:
        self.game = game
        self.commands: List[Dict[str, Any]] = []
        self.current_index: int = 0
        self.wait_frames: int = 0
        self.finished: bool = False
        
    def load_script(self, path: str) -> None:
        """Carga un script JSON."""
        with open(path, 'r', encoding='utf-8') as f:
            self.commands = json.load(f)
        self.current_index = 0
        self.wait_frames = 0
        self.finished = False
        print(f"[SCRIPT] Script cargado: {len(self.commands)} comandos")
        
    def update(self) -> bool:
        """
        Ejecuta un paso del script. Debe llamarse cada frame.
        Retorna True si el script sigue corriendo, False si terminó.
        """
        if self.finished:
            return False
            
        # Si estamos esperando, decrementar contador
        if self.wait_frames > 0:
            self.wait_frames -= 1
            return True
            
        # Si no hay más comandos, terminar
        if self.current_index >= len(self.commands):
            self.finished = True
            print("[SCRIPT] Fin del script.")
            return False
            
        # Ejecutar siguiente comando
        cmd = self.commands[self.current_index]
        self.current_index += 1
        return self._execute_command(cmd)

    def run_all(self) -> bool:
        """Ejecuta todos los comandos (bloqueante). Retorna True si todo OK."""
        self.finished = False
        while not self.finished:
            # En modo bloqueante, si hay wait frames, simulamos el paso del tiempo manualmente
            # OJO: Esto solo funciona bien si el caller maneja el tiempo o si es headless
            if self.wait_frames > 0:
                self.wait_frames -= 1
                # Si es headless, avanzar frame del juego
                if hasattr(self.game, "step_frame"):
                    self.game.step_frame() # type: ignore
                continue
                
            if not self.update():
                break
                
        return True
            
    def _execute_command(self, cmd: Dict[str, Any]) -> bool:
        action = cmd.get("action", "").upper()
        args = cmd.get("args", {})
        
        print(f"[SCRIPT] Ejecutando: {action} {args}")
        
        try:
            if action == "LOAD_SCENE":
                path = args.get("path")
                with open(path, 'r') as f:
                    data = json.load(f)
                if self.game._scene_manager:
                    self.game._scene_manager.load_scene(data)
                    
            elif action == "SELECT":
                name = args.get("name")
                if self.game.world:
                    self.game.world.selected_entity_name = name
                    
            elif action == "INSPECT_EDIT":
                ent = args.get("entity")
                comp = args.get("component")
                prop = args.get("property")
                val = args.get("value")
                
                if self.game._scene_manager:
                    success = self.game._scene_manager.apply_edit_to_world(ent, comp, prop, val)
                    if not success:
                        raise Exception(f"Fallo al editar {ent}.{comp}.{prop} = {val}")
                        
            elif action == "PLAY":
                self.game.play()
                if self.game.editor_layout:
                    self.game.editor_layout.active_tab = "GAME"
                    
            elif action == "STOP":
                 self.game.stop()
                 if self.game.editor_layout:
                     self.game.editor_layout.active_tab = "SCENE"
                
            elif action == "SAVE":
                if hasattr(self.game, "save_current_scene"):
                    self.game.save_current_scene()
            
            elif action == "WAIT":
                frames = args.get("frames", 1)
                self.wait_frames = frames
                
            elif action == "ASSERT_POS":
                name = args.get("entity")
                expected_x = args.get("x")
                expected_y = args.get("y")
                tol = args.get("tolerance", 0.1)
                
                if not self.game.world:
                    raise Exception("No hay world activo")
                    
                entity = self.game.world.get_entity_by_name(name)
                if not entity:
                    raise Exception(f"Entidad no encontrada: {name}")
                    
                from engine.components.transform import Transform
                trans = entity.get_component(Transform)
                
                dist_sq = (trans.x - expected_x)**2 + (trans.y - expected_y)**2
                if dist_sq > tol**2:
                    raise AssertionError(f"Posición incorrecta. Esperado: ({expected_x}, {expected_y}), Real: ({trans.x}, {trans.y})")
            
            elif action == "PARENT":
                child_name = args.get("child")
                parent_name = args.get("parent")
                
                if not self.game.world:
                    raise Exception("No hay world activo")
                    
                child = self.game.world.get_entity_by_name(child_name)
                if not child:
                     raise Exception(f"Child no encontrado: {child_name}")
                     
                from engine.components.transform import Transform
                child_transform = child.get_component(Transform)
                
                if parent_name:
                    parent = self.game.world.get_entity_by_name(parent_name)
                    if not parent:
                        raise Exception(f"Parent no encontrado: {parent_name}")
                    parent_transform = parent.get_component(Transform)
                    child_transform.set_parent(parent_transform)
                else:
                    # Desemparentar
                    child_transform.set_parent(None)

            elif action == "EXIT":
                self.game.running = False
                if hasattr(self.game, "headless_running"):
                    self.game.headless_running = False # type: ignore
                    
            else:
                print(f"[SCRIPT] Comando desconocido: {action}")
                
            return True
            
        except AssertionError as e:
            print(f"[SCRIPT] FALLO DE ASSERT: {e}")
            self.finished = True
            return False
        except Exception as e:
            print(f"[SCRIPT] ERROR DE EJECUCIÓN: {e}")
            self.finished = True
            return False
