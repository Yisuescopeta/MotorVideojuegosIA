from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from engine.ecs.world import World
from engine.levels.component_registry import ComponentRegistry
from engine.scenes.scene_manager import SceneManager


class AutoloadSystem:
    """Carga entidades autoload (singleton) al iniciar el proyecto.

    Adaptado de Godot autoload system.
    """

    def __init__(self, project_root: str = "", registry: Optional[ComponentRegistry] = None) -> None:
        self.project_root: str = project_root
        self._registry: Optional[ComponentRegistry] = registry
        self._loaded_entities: Dict[str, int] = {}

    def load_autoloads(self, world: World, scene_manager: Optional[SceneManager] = None) -> Dict[str, int]:
        """Carga todas las entidades autoload definidas en project_settings.json.

        Args:
            world: El World donde se instancian las entidades.
            scene_manager: SceneManager opcional para usar create_entity_from_data.
                Si es None, se crea la entidad directamente via world.create_entity.

        Returns:
            Dict {name: entity_id} de entidades cargadas.
        """
        settings_path = os.path.join(self.project_root, "settings", "project_settings.json")
        if not os.path.isfile(settings_path):
            return {}

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

        autoloads: Dict[str, Any] = settings.get("autoloads", {})
        if not isinstance(autoloads, dict):
            return {}

        for name, config in autoloads.items():
            if not isinstance(config, dict):
                continue
            if not config.get("singleton", False):
                continue

            scene_path = str(config.get("scene_path", "") or "")
            if not scene_path:
                continue

            full_path = os.path.join(self.project_root, scene_path)
            if not os.path.isfile(full_path):
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    scene_data = json.load(f)

                entities: list[Dict[str, Any]] = scene_data.get("entities", [])
                for entity_data in entities:
                    entity_name = str(entity_data.get("name", "") or name)

                    if scene_manager is not None:
                        scene_manager.create_entity_from_data(entity_data)
                        entity = world.get_entity_by_name(entity_name)
                    else:
                        entity = world.create_entity(entity_name)
                        if entity is not None and self._registry is not None:
                            for comp_name, comp_data in entity_data.get("components", {}).items():
                                try:
                                    component = self._registry.create(comp_name, comp_data)
                                    entity.add_component(component)
                                except Exception:
                                    continue

                    if entity is not None:
                        entity_id: int = entity.id
                        self._loaded_entities[name] = entity_id
            except Exception:
                continue

        return dict(self._loaded_entities)

    def get_autoload(self, name: str) -> Optional[int]:
        """Retorna el entity_id del autoload por nombre.

        Args:
            name: Nombre del autoload registrado.

        Returns:
            El entity_id (int), o None si no existe.
        """
        return self._loaded_entities.get(name)

    def list_autoloads(self) -> list[str]:
        """Retorna los nombres de todos los autoloads cargados.

        Returns:
            Lista de nombres de autoload.
        """
        return list(self._loaded_entities.keys())
