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
        self._data: Dict[str, Any] = data or {"name": name, "entities": [], "rules": []}
    
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
            
            for comp_name, comp_props in components_data.items():
                component = registry.create(comp_name, comp_props)
                if component is not None:
                    entity.add_component(component)
        
        return world
    
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
