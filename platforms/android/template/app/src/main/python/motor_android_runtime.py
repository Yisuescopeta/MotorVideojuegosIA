"""Android Python runtime bridge helpers."""

from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


os.environ.setdefault("PYRAY_FORCE_STUB", "1")
_shared_runtime: "AndroidSharedRuntime | None" = None


class Component:
    def __init__(self, data: dict[str, Any]) -> None:
        object.__setattr__(self, "_data", data)

    def __getattr__(self, name: str) -> Any:
        data = object.__getattribute__(self, "_data")
        if name in data:
            return data[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        object.__getattribute__(self, "_data")[name] = value


class Entity:
    def __init__(self, world: "World", data: dict[str, Any], runtime_id: int) -> None:
        self._world = world
        self._data = data
        self.id = runtime_id
        self.name = str(data.get("name", ""))

    @property
    def active(self) -> bool:
        return bool(self._data.get("active", True))

    @active.setter
    def active(self, value: bool) -> None:
        self._data["active"] = bool(value)

    def get_component_by_name(self, component_name: str) -> Component | None:
        components = self._data.get("components", {})
        component = components.get(str(component_name))
        if isinstance(component, dict):
            return Component(component)
        return None


class World:
    def __init__(self, scene: dict[str, Any]) -> None:
        self.scene = scene
        self.entities = scene.setdefault("entities", [])
        self._entity_ids: dict[int, int] = {}
        self._next_id = 1

    def iter_all_entities(self) -> list[Entity]:
        return [Entity(self, entity, self._runtime_id(entity)) for entity in self.entities if isinstance(entity, dict)]

    def get_entity_by_name(self, entity_name: str) -> Entity | None:
        wanted = str(entity_name)
        for entity in self.iter_all_entities():
            if entity.name == wanted:
                return entity
        return None

    def remove_entity(self, entity_id: int) -> None:
        target = int(entity_id)
        self.entities[:] = [
            entity
            for entity in self.entities
            if not isinstance(entity, dict) or self._runtime_id(entity) != target
        ]

    def destroy_entity(self, entity_id: int) -> None:
        self.remove_entity(entity_id)

    def _runtime_id(self, entity: dict[str, Any]) -> int:
        key = id(entity)
        if key not in self._entity_ids:
            self._entity_ids[key] = self._next_id
            self._next_id += 1
        return self._entity_ids[key]


class ScriptBehaviourContext:
    def __init__(self, world: World, entity_name: str, script_data: dict[str, Any]) -> None:
        self.world = world
        self.entity_name = entity_name
        self.public_data = script_data.setdefault("public_data", {})

    def get_entity(self) -> Entity | None:
        return self.world.get_entity_by_name(self.entity_name)

    def get_entity_by_name(self, entity_name: str) -> Entity | None:
        return self.world.get_entity_by_name(entity_name)

    def get_component(self, component_name: str) -> Component | None:
        entity = self.get_entity()
        if entity is None:
            return None
        return entity.get_component_by_name(component_name)

    def log_info(self, message: str) -> None:
        print(f"[Script:{self.entity_name}] {message}")

    def log_error(self, message: str) -> None:
        print(f"[Script:{self.entity_name}] ERROR {message}")


def run_hook(scene_json: str, hook_name: str, dt: float = 0.0) -> str:
    scene = json.loads(scene_json)
    world = World(scene)
    for entity_data in list(scene.get("entities", [])):
        if not isinstance(entity_data, dict) or not entity_data.get("active", True):
            continue
        components = entity_data.get("components", {})
        script_data = components.get("ScriptBehaviour")
        if not isinstance(script_data, dict) or not script_data.get("enabled", True):
            continue
        module_name = _module_name(script_data)
        if not module_name:
            continue
        try:
            module = importlib.import_module(module_name)
            hook = getattr(module, hook_name, None)
            if hook is None:
                continue
            context = ScriptBehaviourContext(world, str(entity_data.get("name", "")), script_data)
            if hook_name == "on_update":
                hook(context, float(dt or 0.0))
            else:
                hook(context)
        except Exception:
            print(f"[Script:{entity_data.get('name', '')}] {module_name}.{hook_name} failed")
            traceback.print_exc()
    return json.dumps(scene, separators=(",", ":"))


class AndroidSharedRuntime:
    """Chaquopy-facing adapter over the same runtime used by editor PLAY."""

    def __init__(self, base_path: str, config_json: str = "{}") -> None:
        self.base_path = Path(base_path)
        self.config = _loads_object(config_json)
        if str(self.base_path) not in sys.path:
            sys.path.insert(0, str(self.base_path))
        scripts_dir = self.base_path / "scripts"
        if scripts_dir.exists() and str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from engine.levels.component_registry import create_default_registry
        from engine.runtime.content_loader import ContentLoader
        from engine.runtime.shared_game_runtime import SharedGameRuntime

        window = self.config.get("window", {})
        self.loader = ContentLoader(self.base_path)
        self.runtime = SharedGameRuntime(
            loader=self.loader,
            registry=create_default_registry(),
            window_config=window if isinstance(window, dict) else {},
        )
        self.runtime.setup_scripts_path()

    def load_scene(self, scene_path: str) -> str:
        ok = self.runtime.load_scene(str(scene_path or ""))
        return self.snapshot(ok=ok)

    def run_frame(self, dt: float = 1.0 / 60.0, pointer_json: str | None = None) -> str:
        pointer = _loads_object(pointer_json or "{}")
        pointer_state = pointer if pointer else None
        self.runtime.run_frame(float(dt or 0.0), pointer_state=pointer_state)
        return self.snapshot(ok=True)

    def set_entity_transform(self, entity_name: str, x: float, y: float) -> str:
        world = self.runtime.world
        entity = world.get_entity_by_name(str(entity_name)) if world is not None else None
        if entity is not None:
            transform = entity.get_component_by_name("Transform")
            if transform is not None:
                transform.x = float(x)
                transform.y = float(y)
                if hasattr(world, "touch_transform"):
                    world.touch_transform()
                if hasattr(world, "touch_physics"):
                    world.touch_physics()
        return self.snapshot(ok=entity is not None)

    def snapshot(self, *, ok: bool) -> str:
        world = self.runtime.world
        scene = world.serialize() if world is not None else {"entities": [], "rules": [], "feature_metadata": {}}
        return json.dumps(
            {
                "ok": bool(ok),
                "current_scene": self.runtime.current_scene_path or "",
                "frame_count": self.runtime.frame_count,
                "scene": scene,
                "events": self.runtime.get_recent_events(50),
            },
            separators=(",", ":"),
        )

    def shutdown(self) -> str:
        self.runtime.shutdown()
        return json.dumps({"ok": True}, separators=(",", ":"))


def create_shared_runtime(base_path: str, config_json: str = "{}") -> str:
    global _shared_runtime
    try:
        if _shared_runtime is not None:
            _shared_runtime.shutdown()
        _shared_runtime = AndroidSharedRuntime(base_path, config_json)
        config = _loads_object(config_json)
        entry_scene = str(config.get("entry_scene") or _shared_runtime.loader.get_entry_scene())
        return _shared_runtime.load_scene(entry_scene)
    except Exception as exc:
        return _error_payload(exc)


def load_shared_scene(scene_path: str) -> str:
    try:
        if _shared_runtime is None:
            return json.dumps({"ok": False, "error": "shared runtime not initialized"}, separators=(",", ":"))
        return _shared_runtime.load_scene(scene_path)
    except Exception as exc:
        return _error_payload(exc)


def run_shared_frame(dt: float = 1.0 / 60.0, pointer_json: str | None = None) -> str:
    try:
        if _shared_runtime is None:
            return json.dumps({"ok": False, "error": "shared runtime not initialized"}, separators=(",", ":"))
        return _shared_runtime.run_frame(dt, pointer_json)
    except Exception as exc:
        return _error_payload(exc)


def set_entity_transform(entity_name: str, x: float, y: float) -> str:
    try:
        if _shared_runtime is None:
            return json.dumps({"ok": False, "error": "shared runtime not initialized"}, separators=(",", ":"))
        return _shared_runtime.set_entity_transform(entity_name, x, y)
    except Exception as exc:
        return _error_payload(exc)


def shutdown_shared_runtime() -> str:
    global _shared_runtime
    try:
        if _shared_runtime is not None:
            out = _shared_runtime.shutdown()
            _shared_runtime = None
            return out
        return json.dumps({"ok": True}, separators=(",", ":"))
    except Exception as exc:
        _shared_runtime = None
        return _error_payload(exc)


def _module_name(script_data: dict[str, Any]) -> str:
    value = str(script_data.get("module_path", "") or "")
    script_ref = script_data.get("script")
    if not value and isinstance(script_ref, dict):
        value = str(script_ref.get("path", "") or "")
    value = value.replace("\\", "/").strip("/")
    if value.startswith("scripts/"):
        value = value[len("scripts/"):]
    if value.endswith(".py"):
        value = value[:-3]
    return value.replace("/", ".").strip(".")


def _loads_object(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _error_payload(exc: Exception) -> str:
    return json.dumps(
        {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        },
        separators=(",", ":"),
    )
