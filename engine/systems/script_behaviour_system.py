"""
engine/systems/script_behaviour_system.py - Ejecucion de ScriptBehaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
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
    scene_flow_loader: Optional[Callable[[str], bool]] = None

    def get_entity(self):
        return self.world.get_entity_by_name(self.entity_name)

    def get_entity_by_name(self, entity_name: str):
        return self.world.get_entity_by_name(str(entity_name))

    def get_component(self, component_name: str):
        entity = self.get_entity()
        if entity is None:
            return None
        for component in entity.iter_components():
            if type(component).__name__ == component_name:
                return component
        return None

    def log_info(self, message: str) -> None:
        log_info(f"[Script:{self.entity_name}] {message}")

    def log_error(self, message: str) -> None:
        log_err(f"[Script:{self.entity_name}] {message}")

    def load_scene_flow_target(self, key: str) -> bool:
        """Carga una escena conectada por `feature_metadata.scene_flow`."""
        if self.scene_flow_loader is None:
            return False
        return bool(self.scene_flow_loader(str(key)))


class ScriptBehaviourSystem:
    """Ejecuta hooks simples de modulos Python sobre entidades serializables."""

    def __init__(self) -> None:
        self._hot_reload_manager: Any = None
        self._scene_manager: Any = None
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None
        self._scene_flow_loader: Optional[Callable[[str], bool]] = None

    def set_hot_reload_manager(self, manager: Any) -> None:
        self._hot_reload_manager = manager

    def set_scene_manager(self, manager: Any) -> None:
        self._scene_manager = manager

    def set_project_service(self, project_service: Any) -> None:
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

    def set_scene_flow_loader(self, loader: Optional[Callable[[str], bool]]) -> None:
        self._scene_flow_loader = loader

    def on_play(self, world: World) -> None:
        self._invoke_for_world(world, "on_play", None, is_edit_mode=False)

    def on_stop(self, world: World) -> None:
        self._invoke_for_world(world, "on_stop", None, is_edit_mode=False)

    def update(self, world: World, dt: float, is_edit_mode: bool = False) -> bool:
        return self._invoke_for_world(world, "on_update", dt, is_edit_mode=is_edit_mode)

    def invoke_callable(
        self,
        world: World,
        entity_name: str,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            log_err(f"[Script:{entity_name}] Entidad no encontrada para invocar {method_name}")
            return False

        script_behaviour = entity.get_component(ScriptBehaviour)
        if script_behaviour is None or not script_behaviour.enabled:
            log_err(f"[Script:{entity_name}] ScriptBehaviour no disponible para invocar {method_name}")
            return False

        return self._invoke_module_callable(
            entity_name,
            world,
            script_behaviour,
            method_name,
            args=args,
            kwargs=kwargs,
        )

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
        args: tuple[Any, ...] = ()
        if hook_name == "on_update":
            args = (dt,)
        return self._invoke_module_callable(
            entity_name,
            world,
            script_behaviour,
            hook_name,
            args=args,
        )

    def _invoke_module_callable(
        self,
        entity_name: str,
        world: World,
        script_behaviour: ScriptBehaviour,
        callable_name: str,
        *,
        args: tuple[Any, ...] = (),
        kwargs: Optional[dict[str, Any]] = None,
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

        callable_obj = getattr(module, callable_name, None)
        if callable_obj is None:
            return False

        context = self._build_context(world, entity_name, script_behaviour)

        try:
            callable_obj(context, *args, **dict(kwargs or {}))
            return True
        except Exception as exc:
            log_err(f"[Script:{entity_name}] Error en {module_name}.{callable_name}: {exc}")
            return False

    def _build_context(
        self,
        world: World,
        entity_name: str,
        script_behaviour: ScriptBehaviour,
    ) -> ScriptBehaviourContext:
        return ScriptBehaviourContext(
            world=world,
            entity_name=entity_name,
            public_data=script_behaviour.public_data,
            scene_manager=self._scene_manager,
            scene_flow_loader=self._scene_flow_loader,
        )

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
