"""
engine/assets/prefab.py - Sistema de Prefabs

PROPÓSITO:
    Gestionar la creación, guardado e instanciación de Prefabs.
    Un Prefab es una entidad serializada (JSON) que actúa como plantilla.

FUNCIONALIDAD:
    - save_prefab(entity, path): Guarda una entidad como archivo .prefab (JSON).
    - instantiate_prefab(path, world, pos): Crea una nueva entidad desde un archivo .prefab.
"""

import json
import os
from typing import Optional, Dict, Any, Tuple

from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.components.transform import Transform
from engine.levels.component_registry import ComponentRegistry, create_default_registry

class PrefabManager:
    """Gestor estático para operaciones con Prefabs."""
    
    @staticmethod
    def save_prefab(entity: Entity, path: str) -> bool:
        """
        Guarda la entidad en un archivo JSON (.prefab).
        
        Args:
            entity: Entidad a guardar
            path: Ruta absoluta o relativa del archivo destino
            
        Returns:
            True si se guardó correctamente
        """
        try:
            data = entity.to_dict()
            
            # Asegurar que el directorio existe
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
                
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
                
            print(f"[PREFAB] Entity '{entity.name}' saved to {path}")
            return True
        except Exception as e:
            print(f"[PREFAB] Error saving prefab to {path}: {e}")
            return False

    @staticmethod
    def load_prefab_data(path: str) -> Optional[Dict[str, Any]]:
        """Carga los datos crudos de un prefab."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[PREFAB] Error loading prefab {path}: {e}")
            return None

    @staticmethod
    def instantiate_prefab(path: str, world: World, position: Optional[Tuple[float, float]] = None) -> Optional[Entity]:
        """
        Instancia un prefab en el mundo.
        
        Args:
            path: Ruta al archivo .prefab
            world: Mundo donde crear la entidad
            position: (Opcional) Sobrescribe la posición del Transform
            
        Returns:
            La nueva entidad creada o None si falló
        """
        data = PrefabManager.load_prefab_data(path)
        if not data:
            return None
            
        # Nombre base (puede cambiar si ya existe en el mundo, World lo maneja? No, World.create_entity usa el nombre tal cual o permite duplicados?)
        # World.create_entity usa diccionario de nombres. Si existe, sobrescribe o error?
        # Checked world.py: create_entity añade a self.entities (list) y self.entity_map (dict).
        # Si existe, sobrescribe en mapa.
        # Deberíamos generar un nombre único.
        
        base_name = data.get("name", "Prefab")
        unique_name = base_name
        count = 1
        while world.get_entity_by_name(unique_name):
            unique_name = f"{base_name}_{count}"
            count += 1
            
        entity = world.create_entity(unique_name)
        
        # Componentes
        components_data = data.get("components", {})
        registry = create_default_registry()
        
        # Orden de instanciación: Transform primero suele ser útil, pero no crítico.
        
        for comp_name, comp_data in components_data.items():
            # Override posición si se solicita
            if comp_name == "Transform" and position is not None:
                comp_data["x"] = position[0]
                comp_data["y"] = position[1]
                
            component = registry.create(comp_name, comp_data)
            if component:
                entity.add_component(component)
            else:
                print(f"[PREFAB] Warning: Unknown component '{comp_name}' in prefab {path}")
                
        print(f"[PREFAB] Instantiated '{unique_name}' from {os.path.basename(path)}")
        return entity
