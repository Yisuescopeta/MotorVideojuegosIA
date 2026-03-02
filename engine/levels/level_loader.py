"""
engine/levels/level_loader.py - Cargador de niveles desde JSON

PROPÓSITO:
    Lee archivos de nivel en formato JSON y crea las entidades
    correspondientes. También carga reglas para el RuleSystem.

FORMATO DE NIVEL:
    {
        "name": "Level Name",
        "entities": [...],
        "rules": [...]  // Opcional
    }
"""

import json
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from engine.ecs.world import World
from engine.levels.component_registry import ComponentRegistry, create_default_registry

if TYPE_CHECKING:
    from engine.events.rule_system import RuleSystem


class LevelLoader:
    """Cargador de niveles desde archivos JSON."""
    
    def __init__(self, registry: Optional[ComponentRegistry] = None) -> None:
        """
        Inicializa el cargador.
        
        Args:
            registry: Registro de componentes
        """
        self._registry = registry or create_default_registry()
        self._current_level_path: Optional[str] = None
        self._current_level_data: Optional[Dict[str, Any]] = None
        self._rule_system: Optional["RuleSystem"] = None
    
    def set_rule_system(self, rule_system: "RuleSystem") -> None:
        """Asigna el sistema de reglas."""
        self._rule_system = rule_system
    
    @property
    def current_level_name(self) -> str:
        """Nombre del nivel actual."""
        if self._current_level_data is None:
            return "Sin nivel"
        return self._current_level_data.get("name", "Sin nombre")
    
    def load(self, path: str, world: World, clear_world: bool = True) -> bool:
        """
        Carga un nivel desde un archivo JSON.
        
        Args:
            path: Ruta al archivo JSON
            world: World donde crear entidades
            clear_world: Si limpiar el world primero
            
        Returns:
            True si se cargó correctamente
        """
        if not os.path.exists(path):
            print(f"[ERROR] LevelLoader: archivo no encontrado: {path}")
            return False
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                level_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[ERROR] LevelLoader: JSON inválido en {path}: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] LevelLoader: error leyendo {path}: {e}")
            return False
        
        self._current_level_path = path
        self._current_level_data = level_data
        
        return self._load_level_data(level_data, world, clear_world)
    
    def load_from_dict(self, level_data: Dict[str, Any], world: World, clear_world: bool = True) -> bool:
        """Carga un nivel desde un diccionario."""
        self._current_level_path = None
        self._current_level_data = level_data
        return self._load_level_data(level_data, world, clear_world)
    
    def reload(self, world: World) -> bool:
        """Recarga el nivel actual."""
        if self._current_level_path is not None:
            return self.load(self._current_level_path, world, clear_world=True)
        elif self._current_level_data is not None:
            return self._load_level_data(self._current_level_data, world, clear_world=True)
        else:
            print("[WARNING] LevelLoader: no hay nivel para recargar")
            return False
    
    def _load_level_data(self, level_data: Dict[str, Any], world: World, clear_world: bool) -> bool:
        """Procesa los datos del nivel."""
        level_name = level_data.get("name", "Sin nombre")
        entities_data = level_data.get("entities", [])
        rules_data = level_data.get("rules", [])
        
        print(f"[INFO] LevelLoader: cargando '{level_name}'")
        
        if clear_world:
            world.clear()
        
        # Crear entidades
        entities_created = 0
        components_created = 0
        
        for entity_data in entities_data:
            entity_name = entity_data.get("name", f"Entity_{entities_created}")
            components_data = entity_data.get("components", {})
            
            entity = world.create_entity(entity_name)
            entities_created += 1
            
            for comp_name, comp_props in components_data.items():
                component = self._registry.create(comp_name, comp_props)
                if component is not None:
                    entity.add_component(component)
                    components_created += 1
        
        print(f"[INFO] LevelLoader: {entities_created} entidades, {components_created} componentes")
        
        # Cargar reglas si hay RuleSystem
        if self._rule_system is not None and rules_data:
            self._rule_system.set_world(world)
            self._rule_system.load_rules(rules_data)
        
        return True
    
    def get_registry(self) -> ComponentRegistry:
        """Obtiene el registro de componentes."""
        return self._registry
