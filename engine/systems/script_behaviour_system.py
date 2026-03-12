"""
engine/systems/script_behaviour_system.py - Ejecucion de ScriptBehaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from engine.assets.asset_service import AssetService
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
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None

    def set_hot_reload_manager(self, manager: Any) -> None:
        self._hot_reload_manager = manager

    def set_scene_manager(self, manager: Any) -> None:
        self._scene_manager = manager

    def set_project_service(self, project_service: Any) -> None:
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

    def on_play(self, world: World) -> None:
        self._invoke_for_world(world, "on_play", None, is_edit_mode=False)

    def on_stop(self, world: World) -> None:
        self._invoke_for_world(world, "on_stop", None, is_edit_mode=False)

    def update(self, world: World, dt: float, is_edit_mode: bool = False) -> bool:
        return self._invoke_for_world(world, "on_update", dt, is_edit_mode=is_edit_mode)

    def _invoke_for_world(self, world: World, hook_name: str, dt: Optional[float], is_edit_mode: bool) -> bool:
        invoked = False
        for entity in world.get_entities_with(ScriptBehaviour):
            script_behaviour = entity.get_component(ScriptBehaviour)
            if script_behaviour is None or not script_behaviour.enabled:
                continue
            if is_edit_mode and not script_behaviour.run_in_edit_mode:
                continue
            if self._invoke_hook(entity.name, world, script_behaviour, hook_name, dt):
                invoked = True
        return invoked

    def _invoke_hook(
        self,
        entity_name: str,
        world: World,
        script_behaviour: ScriptBehaviour,
        hook_name: str,
        dt: Optional[float],
    ) -> bool:
        module_name = self._resolve_module_name(script_behaviour)
        if not module_name:
            return False

        module = None
        if self._hot_reload_manager is not None:
            module = self._hot_reload_manager.ensure_module_loaded(module_name)

        if module is None:
            log_err(f"[Script:{entity_name}] Modulo no encontrado: {module_name}")
            return False

        hook = getattr(module, hook_name, None)
        if hook is None:
            return False

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
            return True
        except Exception as exc:
            log_err(f"[Script:{entity_name}] Error en {module_name}.{hook_name}: {exc}")
            return False

    def _resolve_module_name(self, script_behaviour: ScriptBehaviour) -> str:
        if self._asset_resolver is not None:
            entry = self._asset_resolver.resolve_entry(script_behaviour.get_script_reference())
            if entry is not None:
                script_behaviour.sync_script_reference(entry.get("reference", {}))
            module_name = self._asset_resolver.resolve_module_name(script_behaviour.get_script_reference())
            if module_name:
                return module_name
        return self._normalize_module_name(script_behaviour.module_path)

    def _normalize_module_name(self, module_path: str) -> str:
        value = module_path.strip().replace("\\", "/")
        if value.endswith(".py"):
            value = value[:-3]
        value = value.strip("/")
        return value.replace("/", ".")
