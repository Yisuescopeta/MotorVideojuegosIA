"""
engine/systems/script_behaviour_system.py - Ejecucion de ScriptBehaviour
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from engine.components.scriptbehaviour import ScriptBehaviour
from engine.editor.console_panel import log_err, log_info
from engine.ecs.world import World


@dataclass
class ScriptBehaviourContext:
    """Contexto explicito que recibe cada hook del script."""

    world: World
    entity_name: str
    public_data: dict[str, Any]
    scene_manager: Any = None

    def get_entity(self):
        return self.world.get_entity_by_name(self.entity_name)

    def get_component(self, component_name: str):
        entity = self.get_entity()
        if entity is None:
            return None
        for component in entity.get_all_components():
            if type(component).__name__ == component_name:
                return component
        return None

    def log_info(self, message: str) -> None:
        log_info(f"[Script:{self.entity_name}] {message}")

    def log_error(self, message: str) -> None:
        log_err(f"[Script:{self.entity_name}] {message}")


class ScriptBehaviourSystem:
    """Ejecuta hooks simples de modulos Python sobre entidades serializables."""

    def __init__(self) -> None:
        self._hot_reload_manager: Any = None
        self._scene_manager: Any = None

    def set_hot_reload_manager(self, manager: Any) -> None:
        self._hot_reload_manager = manager

    def set_scene_manager(self, manager: Any) -> None:
        self._scene_manager = manager

    def on_play(self, world: World) -> None:
        self._invoke_for_world(world, "on_play", None, is_edit_mode=False)

    def on_stop(self, world: World) -> None:
        self._invoke_for_world(world, "on_stop", None, is_edit_mode=False)

    def update(self, world: World, dt: float, is_edit_mode: bool = False) -> None:
        self._invoke_for_world(world, "on_update", dt, is_edit_mode=is_edit_mode)

    def _invoke_for_world(self, world: World, hook_name: str, dt: Optional[float], is_edit_mode: bool) -> None:
        for entity in world.get_entities_with(ScriptBehaviour):
            script_behaviour = entity.get_component(ScriptBehaviour)
            if script_behaviour is None or not script_behaviour.enabled:
                continue
            if is_edit_mode and not script_behaviour.run_in_edit_mode:
                continue
            self._invoke_hook(entity.name, world, script_behaviour, hook_name, dt)

    def _invoke_hook(
        self,
        entity_name: str,
        world: World,
        script_behaviour: ScriptBehaviour,
        hook_name: str,
        dt: Optional[float],
    ) -> None:
        module_name = self._normalize_module_name(script_behaviour.module_path)
        if not module_name:
            return

        module = None
        if self._hot_reload_manager is not None:
            module = self._hot_reload_manager.ensure_module_loaded(module_name)

        if module is None:
            log_err(f"[Script:{entity_name}] Modulo no encontrado: {module_name}")
            return

        hook = getattr(module, hook_name, None)
        if hook is None:
            return

        context = ScriptBehaviourContext(
            world=world,
            entity_name=entity_name,
            public_data=script_behaviour.public_data,
            scene_manager=self._scene_manager,
        )

        try:
            if hook_name == "on_update":
                hook(context, dt)
            else:
                hook(context)
        except Exception as exc:
            log_err(f"[Script:{entity_name}] Error en {module_name}.{hook_name}: {exc}")

    def _normalize_module_name(self, module_path: str) -> str:
        value = module_path.strip().replace("\\", "/")
        if value.endswith(".py"):
            value = value[:-3]
        value = value.strip("/")
        return value.replace("/", ".")
