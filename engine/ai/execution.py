from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from engine.ai.types import ExecutionAction, ExecutionProposal, MutationPolicy, PlanningSession


class ExecutionEngine:
    def build_proposal(self, plan: PlanningSession, mutation_policy: MutationPolicy) -> ExecutionProposal:
        if plan.gaps:
            return ExecutionProposal(
                summary="La ejecucion esta bloqueada por gaps del motor.",
                actions=[],
                validation_plan=[],
                blocked_by_gaps=True,
                requires_confirmation=True,
                risk_notes=["La peticion requiere ampliar el motor antes de crear el juego solicitado."],
            )

        if plan.execution_intent == "create_platformer_slice":
            actions, risks, validations = self._platformer_actions(
                plan.metadata.get("answers", {}),
                mutation_policy,
                requires_python=bool(plan.metadata.get("requires_python")),
            )
            return ExecutionProposal(
                summary="Propuesta para crear un slice jugable de plataformas usando las capacidades actuales del motor.",
                actions=actions,
                validation_plan=validations,
                blocked_by_gaps=False,
                requires_confirmation=True,
                risk_notes=risks,
            )

        if plan.execution_intent == "attach_player_movement_script":
            target_entity = str(plan.metadata.get("target_entity", "") or "Player")
            script_target = self._movement_script_target(target_entity)
            module_path = Path(script_target).stem
            actions = [
                ExecutionAction(
                    id="ensure_player_input_map",
                    action_type="api_call",
                    summary=f"Asegurar InputMap base en {target_entity} para capturar movimiento y salto",
                    args={
                        "method": "add_component",
                        "kwargs": {
                            "entity_name": target_entity,
                            "component_name": "InputMap",
                            "data": {
                                "enabled": True,
                                "move_left": "A,LEFT",
                                "move_right": "D,RIGHT",
                                "action_1": "SPACE",
                            },
                        },
                    },
                    requires_confirmation=mutation_policy.require_confirmation,
                ),
                ExecutionAction(
                    id="ensure_player_rigidbody",
                    action_type="api_call",
                    summary=f"Asegurar RigidBody base en {target_entity} para movimiento scriptado",
                    args={
                        "method": "add_component",
                        "kwargs": {
                            "entity_name": target_entity,
                            "component_name": "RigidBody",
                            "data": {
                                "enabled": True,
                                "velocity_x": 0.0,
                                "velocity_y": 0.0,
                                "gravity_scale": 1.0,
                                "is_grounded": False,
                            },
                        },
                    },
                    requires_confirmation=mutation_policy.require_confirmation,
                ),
                ExecutionAction(
                    id="attach_player_script_behaviour",
                    action_type="api_call",
                    summary=f"Adjuntar ScriptBehaviour a {target_entity} con datos base de movimiento",
                    args={
                        "method": "add_script_behaviour",
                        "kwargs": {
                            "entity_name": target_entity,
                            "module_path": module_path,
                            "public_data": {"speed": 180, "jump_force": 320},
                            "run_in_edit_mode": False,
                            "enabled": True,
                        },
                    },
                    requires_confirmation=mutation_policy.require_confirmation,
                ),
                ExecutionAction(
                    id="player_script_scaffold",
                    action_type="python_write",
                    summary=f"Escribir scaffold Python para el movimiento de {target_entity}",
                    args={"target": script_target},
                    risk="elevated",
                    requires_confirmation=True,
                ),
            ]
            return ExecutionProposal(
                summary=f"Propuesta para anadir un script de movimiento a {target_entity}.",
                actions=actions,
                validation_plan=[
                    f"Comprobar que {target_entity} tiene InputMap, RigidBody y ScriptBehaviour",
                    f"Validar que {script_target} existe",
                    "Entrar en PLAY y asegurar que el ciclo PLAY/STOP sigue funcionando",
                ],
                blocked_by_gaps=False,
                requires_confirmation=True,
                risk_notes=[
                    "Requiere habilitar cambios Python para escribir el scaffold automaticamente.",
                    f"La entidad {target_entity} debe existir en la escena actual.",
                ],
            )

        return ExecutionProposal(
            summary="No hay una receta de ejecucion automatica para esta peticion todavia.",
            actions=[],
            validation_plan=[],
            blocked_by_gaps=False,
            requires_confirmation=True,
            risk_notes=["La planificacion existe, pero la traduccion automatica a acciones no esta implementada para este caso."],
        )

    def apply(self, engine_api, proposal: ExecutionProposal, allow_python: bool, allow_engine_changes: bool) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
        results: List[Dict[str, Any]] = []
        errors: List[str] = []
        for action in proposal.actions:
            if action.action_type == "python_write":
                if not allow_python:
                    errors.append(f"Python change blocked: {action.summary}")
                    continue
                result = self._write_python_scaffold(engine_api, action)
                results.append({"action_id": action.id, "result": result})
                if isinstance(result, dict) and result.get("success") is False:
                    errors.append(f"{action.summary}: {result.get('message', 'python write failed')}")
                continue
            if action.action_type == "engine_change" and not allow_engine_changes:
                errors.append(f"Engine change blocked: {action.summary}")
                continue
            if action.action_type != "api_call":
                errors.append(f"Unsupported action type: {action.action_type}")
                continue
            method_name = action.args.get("method")
            kwargs = dict(action.args.get("kwargs", {}))
            method = getattr(engine_api, method_name, None)
            if method is None:
                errors.append(f"Unknown EngineAPI method: {method_name}")
                continue
            result = method(**kwargs)
            results.append({"action_id": action.id, "result": result})
            if isinstance(result, dict) and result.get("success") is False:
                duplicate_component = method_name == "add_component" and "already exists" in str(result.get("message", "")).lower()
                if duplicate_component:
                    continue
                errors.append(f"{action.summary}: {result.get('message', 'unknown failure')}")
        return (len(errors) == 0, results, errors)

    def _write_python_scaffold(self, engine_api, action: ExecutionAction) -> Dict[str, Any]:
        project_service = getattr(engine_api, "project_service", None)
        if project_service is None or not getattr(project_service, "has_project", False):
            return {"success": False, "message": "Project service not ready for Python scaffold generation."}

        target = str(action.args.get("target", "")).strip()
        if not target:
            return {"success": False, "message": "Python scaffold target is missing."}

        content = self.build_script_content(target)
        target_path = project_service.resolve_path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

        game = getattr(engine_api, "game", None)
        hot_reload = getattr(game, "hot_reload_manager", None)
        if hot_reload is not None:
            hot_reload.scan_directory()

        return {
            "success": True,
            "message": "Python scaffold written.",
            "data": {"path": target_path.as_posix()},
        }

    def build_script_content(self, target: str) -> str:
        target = str(target or "").strip()
        if target.endswith("_movement_generated.py"):
            return self._player_movement_script_template()
        if target == "scripts/generated_platformer_logic.py":
            return self._generic_platformer_script_template()
        return self._generic_script_template(target)

    def _movement_script_target(self, target_entity: str) -> str:
        normalized = "".join(char.lower() if char.isalnum() else "_" for char in target_entity.strip())
        while "__" in normalized:
            normalized = normalized.replace("__", "_")
        normalized = normalized.strip("_") or "player"
        return f"scripts/{normalized}_movement_generated.py"

    def _player_movement_script_template(self) -> str:
        return """from __future__ import annotations


def on_play(context) -> None:
    context.public_data.setdefault("speed", 180.0)
    context.public_data.setdefault("jump_force", 320.0)
    context.public_data.setdefault("facing", 1)


def on_update(context, dt: float) -> None:
    rigidbody = context.get_component("RigidBody")
    input_map = context.get_component("InputMap")
    if rigidbody is None or input_map is None:
        return

    state = dict(getattr(input_map, "last_state", {}) or {})
    horizontal = float(state.get("horizontal", 0.0))
    jump_pressed = float(state.get("action_1", 0.0)) > 0.0

    speed = float(context.public_data.get("speed", 180.0))
    jump_force = float(context.public_data.get("jump_force", 320.0))
    rigidbody.velocity_x = horizontal * speed

    if horizontal > 0.0:
        context.public_data["facing"] = 1
    elif horizontal < 0.0:
        context.public_data["facing"] = -1

    if jump_pressed and bool(getattr(rigidbody, "is_grounded", False)):
        rigidbody.velocity_y = -abs(jump_force)
"""

    def _generic_script_template(self, target: str) -> str:
        module_name = Path(target).stem
        return f"""from __future__ import annotations


def on_play(context) -> None:
    context.log_info("Script '{module_name}' initialized.")


def on_update(context, dt: float) -> None:
    pass
"""

    def _generic_platformer_script_template(self) -> str:
        return """from __future__ import annotations


def on_play(context) -> None:
    context.public_data.setdefault("spawned", True)
    context.public_data.setdefault("notes", "Generated platformer logic scaffold")


def on_update(context, dt: float) -> None:
    # Extend this scaffold with enemy waves, checkpoints or game flow rules.
    pass
"""

    def _platformer_actions(self, answers: Dict[str, Any], mutation_policy: MutationPolicy, requires_python: bool = False) -> Tuple[List[ExecutionAction], List[str], List[str]]:
        actions: List[ExecutionAction] = []
        asset_strategy = str(answers.get("asset_strategy", "placeholders"))
        use_placeholder_texture = "assets/test_spritesheet.png" if asset_strategy == "project_assets" else ""

        actions.append(
            ExecutionAction(
                id="create_player",
                action_type="api_call",
                summary="Crear entidad Player con control lateral, salto y colisiones",
                args={
                    "method": "create_entity",
                    "kwargs": {
                        "name": "Player",
                        "components": {
                            "Transform": {"enabled": True, "x": 120.0, "y": 420.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Sprite": {"enabled": True, "texture_path": use_placeholder_texture, "width": 32, "height": 32, "origin_x": 0.5, "origin_y": 0.5},
                            "Collider": {"enabled": True, "width": 28.0, "height": 28.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "RigidBody": {"enabled": True, "velocity_x": 0.0, "velocity_y": 0.0, "gravity_scale": 1.0, "is_grounded": False},
                            "InputMap": {"enabled": True, "move_left": "A,LEFT", "move_right": "D,RIGHT", "action_1": "SPACE"},
                            "PlayerController2D": {"enabled": True, "move_speed": 180.0, "jump_velocity": -320.0, "air_control": 0.75},
                        },
                    },
                },
                requires_confirmation=mutation_policy.require_confirmation,
            )
        )
        actions.append(
            ExecutionAction(
                id="create_ground",
                action_type="api_call",
                summary="Crear suelo jugable con colision",
                args={
                    "method": "create_entity",
                    "kwargs": {
                        "name": "Ground",
                        "components": {
                            "Transform": {"enabled": True, "x": 400.0, "y": 560.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Sprite": {"enabled": True, "texture_path": use_placeholder_texture, "width": 800, "height": 40, "origin_x": 0.5, "origin_y": 0.5},
                            "Collider": {"enabled": True, "width": 800.0, "height": 40.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                },
                requires_confirmation=mutation_policy.require_confirmation,
            )
        )

        if str(answers.get("camera_style", "follow_platformer")) == "follow_platformer":
            actions.append(
                ExecutionAction(
                    id="create_camera",
                    action_type="api_call",
                    summary="Crear camara primaria siguiendo al jugador",
                    args={
                        "method": "create_camera2d",
                        "kwargs": {
                            "name": "MainCamera",
                            "transform": {"x": 320.0, "y": 180.0},
                            "camera": {
                                "offset_x": 320.0,
                                "offset_y": 180.0,
                                "zoom": 1.0,
                                "follow_entity": "Player",
                                "framing_mode": "platformer",
                            },
                        },
                    },
                    requires_confirmation=mutation_policy.require_confirmation,
                )
            )

        if str(answers.get("hud", "none")) == "basic_hud":
            actions.extend(
                [
                    ExecutionAction(
                        id="create_canvas",
                        action_type="api_call",
                        summary="Crear canvas para HUD basico",
                        args={"method": "create_entity", "kwargs": {"name": "HUDCanvas", "components": {"Canvas": {"enabled": True}}}},
                        requires_confirmation=mutation_policy.require_confirmation,
                    ),
                    ExecutionAction(
                        id="create_hud_label",
                        action_type="api_call",
                        summary="Crear texto UI de HUD inicial",
                        args={
                            "method": "create_entity",
                            "kwargs": {
                                "name": "HUDLabel",
                                "components": {
                                    "RectTransform": {"enabled": True, "anchored_x": 20.0, "anchored_y": 20.0, "width": 220.0, "height": 32.0, "anchor_min_x": 0.0, "anchor_min_y": 0.0, "anchor_max_x": 0.0, "anchor_max_y": 0.0},
                                    "UIText": {"enabled": True, "text": "Lives: 3", "font_size": 20, "color": [255, 255, 255, 255]},
                                },
                            },
                        },
                        requires_confirmation=mutation_policy.require_confirmation,
                    ),
                ]
            )

        enemies_value = str(answers.get("enemies", "")).strip().lower()
        if enemies_value and enemies_value not in {"no", "none", "ninguno", "0"}:
            actions.append(
                ExecutionAction(
                    id="create_enemy",
                    action_type="api_call",
                    summary="Crear enemigo placeholder para el primer slice",
                    args={
                        "method": "create_entity",
                        "kwargs": {
                            "name": "Enemy_01",
                            "components": {
                                "Transform": {"enabled": True, "x": 520.0, "y": 420.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                                "Sprite": {"enabled": True, "texture_path": use_placeholder_texture, "width": 32, "height": 32, "origin_x": 0.5, "origin_y": 0.5},
                                "Collider": {"enabled": True, "width": 28.0, "height": 28.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            },
                        },
                    },
                    requires_confirmation=mutation_policy.require_confirmation,
                )
            )

        obstacle_value = str(answers.get("obstacles", "")).strip().lower()
        if obstacle_value and obstacle_value not in {"none", "ninguno", "no"}:
            actions.append(
                ExecutionAction(
                    id="create_obstacle",
                    action_type="api_call",
                    summary="Crear obstaculo placeholder para el slice inicial",
                    args={
                        "method": "create_entity",
                        "kwargs": {
                            "name": "Obstacle_01",
                            "components": {
                                "Transform": {"enabled": True, "x": 340.0, "y": 500.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                                "Sprite": {"enabled": True, "texture_path": use_placeholder_texture, "width": 64, "height": 24, "origin_x": 0.5, "origin_y": 0.5},
                                "Collider": {"enabled": True, "width": 64.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            },
                        },
                    },
                    requires_confirmation=mutation_policy.require_confirmation,
                )
            )

        if requires_python:
            actions.append(
                ExecutionAction(
                    id="python_scaffold",
                    action_type="python_write",
                    summary="Preparar scaffold de script Python para logica personalizada solicitada",
                    args={"target": "scripts/generated_platformer_logic.py"},
                    risk="elevated",
                    requires_confirmation=True,
                )
            )

        validations = [
            "Verificar que Player, Ground y MainCamera existen",
            "Entrar en PLAY, avanzar algunos frames y volver a EDIT",
            "Confirmar que el Player sigue visible y el proyecto queda en estado consistente",
        ]
        risks = [
            "Las acciones modifican la escena actual del proyecto activo.",
            "Los cambios de Python estan bloqueados hasta que el usuario los permita.",
        ]
        return actions, risks, validations
