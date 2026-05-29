"""Android ScriptBehaviour bridge helpers."""

from __future__ import annotations

import importlib
import json
import traceback
from typing import Any


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
