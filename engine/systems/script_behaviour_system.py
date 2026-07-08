"""
engine/systems/script_behaviour_system.py - Ejecucion de ScriptBehaviour.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

from engine.assets.asset_service import AssetService
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.core.runtime_logging import log_err, log_info
from engine.ecs.world import World
from engine.runtime.runtime_input import NULL_RUNTIME_INPUT
from engine.runtime.runtime_picking import NULL_RUNTIME_RENDER_QUERIES

ScriptHook = Callable[..., Any]
ScriptMembershipSignature = tuple[tuple[int, str, int], ...]


@dataclass
class ScriptBehaviourContext:
    """Contexto explicito que recibe cada hook del script."""

    world: World
    entity_name: str
    public_data: dict[str, Any]
    scene_manager: Any = None
    scene_flow_loader: Optional[Callable[[str], bool]] = None
    input: Any = NULL_RUNTIME_INPUT
    render: Any = NULL_RUNTIME_RENDER_QUERIES
    picking: Any = NULL_RUNTIME_RENDER_QUERIES

    def get_entity(self):
        return self.world.get_entity_by_name(self.entity_name)

    def get_entity_by_name(self, entity_name: str):
        return self.world.get_entity_by_name(str(entity_name))

    def get_component(self, component_name: str):
        entity = self.get_entity()
        if entity is None:
            return None
        return entity.get_component_by_name(component_name)

    def log_info(self, message: str) -> None:
        log_info(f"[Script:{self.entity_name}] {message}")

    def log_error(self, message: str) -> None:
        log_err(f"[Script:{self.entity_name}] {message}")

    def load_scene_flow_target(self, key: str) -> bool:
        """Carga una escena conectada por `feature_metadata.scene_flow`."""
        if self.scene_flow_loader is None:
            return False
        return bool(self.scene_flow_loader(str(key)))


@dataclass
class CompiledScriptBehaviour:
    """ScriptBehaviour resuelto para ejecucion runtime."""

    entity_name: str
    script_behaviour: ScriptBehaviour
    module_name: str
    context: ScriptBehaviourContext
    on_play: Optional[ScriptHook] = None
    on_update: Optional[ScriptHook] = None
    on_stop: Optional[ScriptHook] = None


class ScriptBehaviourSystem:
    """Ejecuta hooks simples de modulos Python sobre entidades serializables."""

    def __init__(self) -> None:
        self._hot_reload_manager: Any = None
        self._scene_manager: Any = None
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None
        self._scene_flow_loader: Optional[Callable[[str], bool]] = None
        self._runtime_input: Any = NULL_RUNTIME_INPUT
        self._runtime_render_queries: Any = NULL_RUNTIME_RENDER_QUERIES
        self._runtime_picking: Any = NULL_RUNTIME_RENDER_QUERIES
        self._runtime_compiled_scripts: list[CompiledScriptBehaviour] = []
        self._runtime_world: World | None = None
        self._runtime_world_structure_version: int | None = None
        self._runtime_script_membership_signature: ScriptMembershipSignature = ()
        self._runtime_cache_dirty: bool = False
        self._module_mtimes: dict[str, float] = {}

    def set_hot_reload_manager(self, manager: Any) -> None:
        self._hot_reload_manager = manager
        self._runtime_cache_dirty = True

    def set_scene_manager(self, manager: Any) -> None:
        self._scene_manager = manager
        self._runtime_cache_dirty = True

    def set_project_service(self, project_service: Any) -> None:
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None
        self._runtime_cache_dirty = True

    def set_scene_flow_loader(self, loader: Optional[Callable[[str], bool]]) -> None:
        self._scene_flow_loader = loader
        self._runtime_cache_dirty = True

    def set_runtime_services(
        self,
        *,
        input_service: Any = None,
        render_service: Any = None,
        picking_service: Any = None,
    ) -> None:
        self._runtime_input = input_service if input_service is not None else NULL_RUNTIME_INPUT
        self._runtime_render_queries = render_service if render_service is not None else NULL_RUNTIME_RENDER_QUERIES
        self._runtime_picking = picking_service if picking_service is not None else self._runtime_render_queries
        self._runtime_cache_dirty = True

    def on_play(self, world: World) -> None:
        self._compile_runtime_scripts(world)
        for compiled in self._runtime_compiled_scripts:
            self._invoke_compiled_hook(compiled, "on_play")

    def on_stop(self, world: World) -> None:
        if self._runtime_world is world and self._runtime_compiled_scripts:
            for compiled in self._runtime_compiled_scripts:
                self._invoke_compiled_hook(compiled, "on_stop")
        else:
            self._invoke_for_world(world, "on_stop", None, is_edit_mode=False)
        self._clear_runtime_cache()

    def update(self, world: World, dt: float, is_edit_mode: bool = False) -> bool:
        if not is_edit_mode:
            return self._invoke_runtime_update(world, dt)
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

    def _invoke_runtime_update(self, world: World, dt: float) -> bool:
        if self._runtime_cache_needs_rebuild(world):
            self._compile_runtime_scripts(world)

        if self._runtime_cache_invalidated_by_hot_reload():
            self._compile_runtime_scripts(world)

        invoked = False
        for compiled in self._runtime_compiled_scripts:
            if self._invoke_compiled_hook(compiled, "on_update", args=(dt,)):
                invoked = True
        return invoked

    def _runtime_cache_needs_rebuild(self, world: World) -> bool:
        if self._runtime_world is not world or self._runtime_cache_dirty:
            return True
        if self._runtime_world_structure_version != world.structure_version:
            return True
        return self._runtime_script_membership_signature != self._script_membership_signature(world)

    def _compile_runtime_scripts(self, world: World) -> None:
        compiled_scripts: list[CompiledScriptBehaviour] = []
        for entity in world.get_entities_with(ScriptBehaviour):
            script_behaviour = entity.get_component(ScriptBehaviour)
            if script_behaviour is None or not script_behaviour.enabled:
                continue

            module_name = self._resolve_module_name(script_behaviour)
            if not module_name:
                continue

            module = self._load_module(entity.name, module_name)
            if module is None:
                continue

            compiled_scripts.append(
                CompiledScriptBehaviour(
                    entity_name=entity.name,
                    script_behaviour=script_behaviour,
                    module_name=module_name,
                    context=self._build_context(world, entity.name, script_behaviour),
                    on_play=getattr(module, "on_play", None),
                    on_update=getattr(module, "on_update", None),
                    on_stop=getattr(module, "on_stop", None),
                )
            )

        self._runtime_compiled_scripts = compiled_scripts
        self._runtime_world = world
        self._runtime_world_structure_version = world.structure_version
        self._runtime_script_membership_signature = self._script_membership_signature(world)
        self._runtime_cache_dirty = False

    def _script_membership_signature(self, world: World) -> ScriptMembershipSignature:
        signature: list[tuple[int, str, int]] = []
        for entity in world.get_entities_with(ScriptBehaviour):
            script_behaviour = entity.get_component(ScriptBehaviour)
            if script_behaviour is None or not script_behaviour.enabled:
                continue
            signature.append((entity.id, entity.name, id(script_behaviour)))
        return tuple(signature)

    def _runtime_cache_invalidated_by_hot_reload(self) -> bool:
        if self._hot_reload_manager is None:
            for compiled in self._runtime_compiled_scripts:
                module = sys.modules.get(compiled.module_name)
                source_path = getattr(module, "__file__", "") if module is not None else ""
                if not source_path:
                    continue
                try:
                    current_mtime = os.path.getmtime(source_path)
                except OSError:
                    continue
                previous_mtime = self._module_mtimes.get(compiled.module_name)
                if previous_mtime is not None and current_mtime > previous_mtime:
                    sys.modules.pop(compiled.module_name, None)
                    self._runtime_cache_dirty = True
                    return True
            return False

        modules: dict[str, Any] = {}
        for compiled in self._runtime_compiled_scripts:
            if compiled.module_name in modules:
                continue
            module = self._hot_reload_manager.ensure_module_loaded(compiled.module_name)
            if module is None:
                self._runtime_cache_dirty = True
                return True
            modules[compiled.module_name] = module

        for compiled in self._runtime_compiled_scripts:
            module = modules.get(compiled.module_name)
            if module is None:
                continue
            if (
                getattr(module, "on_play", None) is not compiled.on_play
                or getattr(module, "on_update", None) is not compiled.on_update
                or getattr(module, "on_stop", None) is not compiled.on_stop
            ):
                self._runtime_cache_dirty = True
                return True
        return False

    def _invoke_compiled_hook(
        self,
        compiled: CompiledScriptBehaviour,
        hook_name: str,
        *,
        args: tuple[Any, ...] = (),
    ) -> bool:
        entity = compiled.context.world.get_entity_by_name(compiled.entity_name)
        if entity is None or not entity.active:
            return False
        script_behaviour = entity.get_component(ScriptBehaviour)
        if script_behaviour is None:
            return False
        if script_behaviour is not compiled.script_behaviour:
            return False
        if not script_behaviour.enabled:
            return False

        callable_obj = getattr(compiled, hook_name)
        if callable_obj is None:
            return False

        try:
            callable_obj(compiled.context, *args)
            return True
        except Exception as exc:
            log_err(f"[Script:{compiled.entity_name}] Error en {compiled.module_name}.{hook_name}: {exc}")
            return False

    def _clear_runtime_cache(self) -> None:
        self._runtime_compiled_scripts = []
        self._runtime_world = None
        self._runtime_world_structure_version = None
        self._runtime_script_membership_signature = ()
        self._runtime_cache_dirty = False

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

        module = self._load_module(entity_name, module_name)
        if module is None:
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

    def _load_module(self, entity_name: str, module_name: str) -> Any:
        module = None
        if self._hot_reload_manager is not None:
            module = self._hot_reload_manager.ensure_module_loaded(module_name)

        if module is None:
            # Fallback: use standard importlib for exported runtime (no hot-reload)
            try:
                import importlib
                module = importlib.import_module(module_name)
            except ImportError:
                pass

        if module is None and self._asset_resolver is not None:
            script_path = self._asset_resolver.resolve_path(f"scripts/{module_name.replace('.', '/')}.py")
            if script_path:
                try:
                    import importlib.util
                    import sys

                    spec = importlib.util.spec_from_file_location(module_name, script_path)
                    if spec is not None and spec.loader is not None:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                except (ImportError, OSError):
                    module = None

        if module is None:
            log_err(f"[Script:{entity_name}] Modulo no encontrado: {module_name}")
        else:
            source_path = getattr(module, "__file__", "")
            if source_path:
                try:
                    self._module_mtimes[module_name] = os.path.getmtime(source_path)
                except OSError:
                    pass
        return module

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
            input=self._runtime_input,
            render=self._runtime_render_queries,
            picking=self._runtime_picking,
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
