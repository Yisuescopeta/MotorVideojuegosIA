"""
cli/script_executor.py - Ejecutor de scripts de automatizaciÃ³n

PROPÃ“SITO:
    Ejecuta una lista de comandos secuenciales sobre el juego.
    Permite simular acciones de usuario y verificar estados.

COMANDOS SOPORTADOS:
    - OPEN_PROJECT <path>
    - LOAD_SCENE <path>
    - CREATE_ENTITY <name>
    - DELETE_ENTITY <name>
    - ADD_COMPONENT <entity> <component>
    - REMOVE_COMPONENT <entity> <component>
    - SET_COMPONENT_ENABLED <entity> <component> <enabled>
    - SET_ENTITY_META <entity> <property> <value>
    - CREATE_CAMERA2D <name>
    - CREATE_INPUT_MAP <name>
    - SET_INPUT_BINDING <entity> <action> <value>
    - INJECT_INPUT <entity> <state> <frames>
    - CREATE_AUDIO_SOURCE <name>
    - ADD_SCRIPT_BEHAVIOUR <entity>
    - SET_SCRIPT_PUBLIC_DATA <entity> <public_data>
    - SELECT <entity_name>
    - INSPECT_EDIT <entity:component:property> <value>
    - AUDIO_PLAY <entity_name>
    - AUDIO_STOP <entity_name>
    - WAIT <frames>
    - SNAPSHOT_SAVE
    - SNAPSHOT_LOAD
    - SET_EDITOR_STATE <state>
    - UNDO
    - REDO
    - ASSERT_POS <entity> <x> <y> <tolerance>
    - EXIT
"""

import json
from typing import Any, Dict, List

from engine.core.game import Game


class ScriptExecutor:
    """
    Ejecuta scripts de prueba/automatizaciÃ³n sobre una instancia de Game.
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
        Retorna True si el script sigue corriendo, False si terminÃ³.
        """
        if self.finished:
            return False

        # Si estamos esperando, decrementar contador
        if self.wait_frames > 0:
            self.wait_frames -= 1
            return True

        # Si no hay mÃ¡s comandos, terminar
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
            if action == "OPEN_PROJECT":
                path = args.get("path", "")
                if not path or not self.game.open_project(path):
                    raise Exception(f"No se pudo abrir proyecto: {path}")

            elif action == "LOAD_SCENE":
                path = args.get("path")
                with open(path, 'r') as f:
                    data = json.load(f)
                if self.game._scene_manager:
                    self.game._scene_manager.load_scene(data)

            elif action == "CREATE_ENTITY":
                name = args.get("name", "New Entity")
                if not self.game._scene_manager or not self.game._scene_manager.create_entity(name):
                    raise Exception(f"No se pudo crear entidad: {name}")

            elif action == "DELETE_ENTITY":
                name = args.get("name")
                if not self.game._scene_manager or not self.game._scene_manager.remove_entity(name):
                    raise Exception(f"No se pudo eliminar entidad: {name}")

            elif action == "ADD_COMPONENT":
                entity_name = args.get("entity")
                component_name = args.get("component")
                component_data = args.get("data", {})
                if not self.game._scene_manager or not self.game._scene_manager.add_component_to_entity(entity_name, component_name, component_data):
                    raise Exception(f"No se pudo aÃ±adir componente {component_name} a {entity_name}")

            elif action == "REMOVE_COMPONENT":
                entity_name = args.get("entity")
                component_name = args.get("component")
                if not self.game._scene_manager or not self.game._scene_manager.remove_component_from_entity(entity_name, component_name):
                    raise Exception(f"No se pudo eliminar componente {component_name} de {entity_name}")

            elif action == "SET_COMPONENT_ENABLED":
                entity_name = args.get("entity")
                component_name = args.get("component")
                enabled = bool(args.get("enabled", True))
                if not self.game._scene_manager or not self.game._scene_manager.set_component_enabled(entity_name, component_name, enabled):
                    raise Exception(f"No se pudo cambiar enabled de {entity_name}.{component_name}")

            elif action == "SET_ENTITY_META":
                entity_name = args.get("entity")
                property_name = args.get("property")
                value = args.get("value")
                if not self.game._scene_manager or not self.game._scene_manager.update_entity_property(entity_name, property_name, value):
                    raise Exception(f"No se pudo actualizar {entity_name}.{property_name}")

            elif action == "CREATE_CAMERA2D":
                name = args.get("name", "MainCamera")
                camera_components: Dict[str, Dict[str, Any]] = {
                    "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "Camera2D": {
                        "enabled": True,
                        "offset_x": 0.0,
                        "offset_y": 0.0,
                        "zoom": 1.0,
                        "rotation": 0.0,
                        "is_primary": True,
                        "follow_entity": "",
                        "framing_mode": "platformer",
                        "dead_zone_width": 0.0,
                        "dead_zone_height": 0.0,
                        "clamp_left": None,
                        "clamp_right": None,
                        "clamp_top": None,
                        "clamp_bottom": None,
                        "recenter_on_play": True,
                    },
                }
                camera_components["Transform"].update(args.get("transform", {}))
                camera_components["Camera2D"].update(args.get("camera", {}))
                if not self.game._scene_manager or not self.game._scene_manager.create_entity(name, camera_components):
                    raise Exception(f"No se pudo crear Camera2D: {name}")

            elif action == "CREATE_INPUT_MAP":
                name = args.get("name", "InputMap")
                input_components: Dict[str, Dict[str, Any]] = {
                    "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "InputMap": {
                        "enabled": True,
                        "move_left": "A,LEFT",
                        "move_right": "D,RIGHT",
                        "move_up": "W,UP",
                        "move_down": "S,DOWN",
                        "action_1": "SPACE",
                        "action_2": "ENTER",
                    },
                }
                input_components["InputMap"].update(args.get("bindings", {}))
                if not self.game._scene_manager or not self.game._scene_manager.create_entity(name, input_components):
                    raise Exception(f"No se pudo crear InputMap: {name}")

            elif action == "SET_INPUT_BINDING":
                entity_name = args.get("entity")
                action_name = args.get("binding")
                value = args.get("value")
                if not self.game._scene_manager or not self.game._scene_manager.apply_edit_to_world(entity_name, "InputMap", action_name, value):
                    raise Exception(f"No se pudo editar InputMap {entity_name}.{action_name}")

            elif action == "INJECT_INPUT":
                entity_name = args.get("entity")
                state = args.get("state", {})
                frames = int(args.get("frames", 1))
                if self.game._input_system is None:
                    raise Exception("No hay InputSystem para inyectar input")
                self.game._input_system.inject_state(entity_name, state, frames)

            elif action == "CREATE_AUDIO_SOURCE":
                name = args.get("name", "AudioSource")
                audio_components: Dict[str, Dict[str, Any]] = {
                    "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "AudioSource": {
                        "enabled": True,
                        "asset": {"guid": "", "path": ""},
                        "asset_path": "",
                        "volume": 1.0,
                        "pitch": 1.0,
                        "loop": False,
                        "play_on_awake": False,
                        "spatial_blend": 0.0,
                    },
                }
                audio_components["Transform"].update(args.get("transform", {}))
                audio_components["AudioSource"].update(args.get("audio", {}))
                if not self.game._scene_manager or not self.game._scene_manager.create_entity(name, audio_components):
                    raise Exception(f"No se pudo crear AudioSource: {name}")

            elif action == "ADD_SCRIPT_BEHAVIOUR":
                entity_name = args.get("entity")
                module_path = args.get("module_path", "")
                component_data = {
                    "enabled": bool(args.get("enabled", True)),
                    "script": args.get("script", {"guid": "", "path": ""}),
                    "module_path": module_path,
                    "run_in_edit_mode": bool(args.get("run_in_edit_mode", False)),
                    "public_data": args.get("public_data", {}),
                }
                if not self.game._scene_manager or not self.game._scene_manager.add_component_to_entity(entity_name, "ScriptBehaviour", component_data):
                    raise Exception(f"No se pudo aÃ±adir ScriptBehaviour a {entity_name}")

            elif action == "SET_SCRIPT_PUBLIC_DATA":
                entity_name = args.get("entity")
                public_data = args.get("public_data", {})
                if not self.game._scene_manager or not self.game._scene_manager.apply_edit_to_world(entity_name, "ScriptBehaviour", "public_data", public_data):
                    raise Exception(f"No se pudo actualizar public_data de {entity_name}")

            elif action == "SELECT":
                name = args.get("name")
                if self.game._scene_manager:
                    self.game._scene_manager.set_selected_entity(name)
                elif self.game.world:
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

            elif action == "AUDIO_PLAY":
                name = args.get("entity")
                if self.game.world is None or self.game.audio_system is None or not self.game.audio_system.play(self.game.world, name):
                    raise Exception(f"No se pudo reproducir audio en {name}")

            elif action == "AUDIO_STOP":
                name = args.get("entity")
                if self.game.world is None or self.game.audio_system is None or not self.game.audio_system.stop(self.game.world, name):
                    raise Exception(f"No se pudo detener audio en {name}")

            elif action == "WAIT":
                frames = args.get("frames", 1)
                self.wait_frames = frames

            elif action == "SET_EDITOR_STATE":
                if self.game._project_service is None:
                    raise Exception("No hay ProjectService activo")
                self.game._project_service.save_editor_state(args.get("state", {}))

            elif action == "UNDO":
                if not self.game.undo():
                    raise Exception("No se pudo deshacer")

            elif action == "REDO":
                if not self.game.redo():
                    raise Exception("No se pudo rehacer")

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
                if trans is None:
                    raise Exception(f"Transform no encontrado: {name}")

                dist_sq = (trans.x - expected_x)**2 + (trans.y - expected_y)**2
                if dist_sq > tol**2:
                    raise AssertionError(f"PosiciÃ³n incorrecta. Esperado: ({expected_x}, {expected_y}), Real: ({trans.x}, {trans.y})")

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
                if child_transform is None:
                    raise Exception(f"Transform no encontrado: {child_name}")

                if parent_name:
                    parent = self.game.world.get_entity_by_name(parent_name)
                    if not parent:
                        raise Exception(f"Parent no encontrado: {parent_name}")
                    parent_transform = parent.get_component(Transform)
                    if parent_transform is None:
                        raise Exception(f"Transform no encontrado: {parent_name}")
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
            print(f"[SCRIPT] ERROR DE EJECUCIÃ“N: {e}")
            self.finished = True
            return False
