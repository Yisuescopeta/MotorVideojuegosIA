"""
engine/scenes/scene.py - Escena con datos originales del nivel

PROPÓSITO:
    Scene almacena los datos originales del nivel en formato
    serializable (diccionario). No se modifica durante PLAY.

FLUJO:
    1. LevelLoader carga JSON → Scene.data
    2. Scene.create_world() → World para EDIT
    3. play() → World.clone() → RuntimeWorld
    4. stop() → Scene.create_world() → World restaurado

EJEMPLO:
    scene = Scene("Demo", level_data)
    world = scene.create_world(registry)
"""

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.levels.component_registry import ComponentRegistry


class Scene:
    """
    Escena que contiene los datos originales del nivel.
    
    La Scene es inmutable durante PLAY. Sirve como fuente
    de verdad para restaurar el World cuando se detiene.
    """
    
    def __init__(self, name: str = "Untitled", data: Optional[Dict[str, Any]] = None) -> None:
        """
        Inicializa una escena.
        
        Args:
            name: Nombre de la escena
            data: Datos del nivel en formato JSON
        """
        self._name: str = name
        self._data: Dict[str, Any] = data or {
            "name": name,
            "entities": [],
            "rules": [],
            "feature_metadata": {},
        }
        self._data.setdefault("name", name)
        self._data.setdefault("entities", [])
        self._data.setdefault("rules", [])
        self._data.setdefault("feature_metadata", {})
    
    @property
    def name(self) -> str:
        """Nombre de la escena."""
        return self._name
    
    @property
    def data(self) -> Dict[str, Any]:
        """Datos originales del nivel (solo lectura)."""
        return self._data
    
    @property
    def entities_data(self) -> list:
        """Lista de datos de entidades."""
        return self._data.get("entities", [])
    
    @property
    def rules_data(self) -> list:
        """Lista de reglas."""
        return self._data.get("rules", [])

    @property
    def feature_metadata(self) -> Dict[str, Any]:
        """Metadatos adicionales de la escena."""
        return self._data.setdefault("feature_metadata", {})
    
    def create_world(self, registry: "ComponentRegistry") -> "World":
        """
        Crea un World nuevo desde los datos de la escena.
        
        Args:
            registry: Registro de componentes para instanciación
            
        Returns:
            World con todas las entidades de la escena
        """
        from engine.ecs.world import World
        
        world = World()
        
        for entity_data in self.entities_data:
            entity_name = entity_data.get("name", "Entity")
            components_data = entity_data.get("components", {})
            
            entity = world.create_entity(entity_name)
            entity.active = entity_data.get("active", True)
            entity.tag = entity_data.get("tag", "Untagged")
            entity.layer = entity_data.get("layer", "Default")
            
            for comp_name, comp_props in components_data.items():
                component = registry.create(comp_name, comp_props)
                if component is not None:
                    entity.add_component(component)
        
        return world
    
    def update_component(
        self, 
        entity_name: str, 
        component_name: str, 
        property_name: str, 
        value: Any
    ) -> bool:
        """
        Actualiza una propiedad de un componente en los datos de la escena.
        
        Esta es la forma segura de modificar la escena desde el inspector.
        Solo modifica los datos internos (_data), no el World.
        
        Args:
            entity_name: Nombre de la entidad
            component_name: Nombre del componente (ej: "Transform")
            property_name: Nombre de la propiedad (ej: "x")
            value: Nuevo valor
            
        Returns:
            True si se actualizó correctamente, False si no se encontró
        """
        for entity_data in self._data.get("entities", []):
            if entity_data.get("name") == entity_name:
                components = entity_data.get("components", {})
                if component_name in components:
                    components[component_name][property_name] = value
                    print(f"[EDIT] Scene: {entity_name}.{component_name}.{property_name} = {value}")
                    return True
        return False

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        """Actualiza un metadato de entidad serializable."""
        for entity_data in self._data.get("entities", []):
            if entity_data.get("name") == entity_name:
                entity_data[property_name] = value
                return True
        return False

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        """Reemplaza por completo el payload serializable de un componente."""
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if component_name not in components:
            return False
        components[component_name] = component_data
        return True

    def add_entity(self, entity_data: Dict[str, Any]) -> bool:
        """Añade una nueva entidad a la escena."""
        if self.find_entity(entity_data.get("name", "")) is not None:
            return False
        self._data.setdefault("entities", []).append(entity_data)
        return True

    def remove_entity(self, entity_name: str) -> bool:
        """Elimina una entidad por nombre."""
        entities = self._data.get("entities", [])
        for index, entity_data in enumerate(entities):
            if entity_data.get("name") == entity_name:
                del entities[index]
                return True
        return False

    def add_component(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        """Añade o reemplaza un componente en una entidad."""
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        components[component_name] = component_data
        return True

    def remove_component(self, entity_name: str, component_name: str) -> bool:
        """Elimina un componente de una entidad."""
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if component_name not in components:
            return False
        del components[component_name]
        return True

    def set_feature_metadata(self, key: str, value: Any) -> None:
        """Registra metadatos de escena usados por la orquestacion o tooling."""
        self.feature_metadata[key] = value

    def find_entity(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """Busca una entidad serializada por nombre."""
        for entity_data in self._data.get("entities", []):
            if entity_data.get("name") == entity_name:
                return entity_data
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa la escena a diccionario."""
        return self._data.copy()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        """Crea una Scene desde un diccionario."""
        name = data.get("name", "Untitled")
        return cls(name=name, data=data)
    
    def __repr__(self) -> str:
        entity_count = len(self.entities_data)
        return f"Scene(name='{self._name}', entities={entity_count})"
