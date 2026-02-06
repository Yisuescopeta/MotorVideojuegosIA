"""
engine/ecs/world.py - Contenedor de entidades del juego

PROPÓSITO:
    World es el contenedor principal que almacena todas las entidades.
    Incluye clone() para crear copias para RuntimeWorld.
"""

from typing import TypeVar

from engine.ecs.entity import Entity
from engine.ecs.component import Component

T = TypeVar("T", bound=Component)


class World:
    """Contenedor principal de todas las entidades del juego."""
    
    def __init__(self) -> None:
        """Inicializa un mundo vacío."""
        self._entities: dict[int, Entity] = {}
        self.selected_entity_name: str | None = None
    
    def create_entity(self, name: str = "Entity") -> Entity:
        """Crea una nueva entidad y la registra."""
        entity = Entity(name)
        self._entities[entity.id] = entity
        return entity
    
    def add_entity(self, entity: Entity) -> None:
        """Añade una entidad existente al mundo."""
        self._entities[entity.id] = entity
    
    def remove_entity(self, entity_id: int) -> None:
        """Elimina una entidad del mundo por su ID."""
        if entity_id in self._entities:
            del self._entities[entity_id]
    
    def destroy_entity(self, entity_id: int) -> None:
        """Alias de remove_entity para compatibilidad."""
        self.remove_entity(entity_id)
    
    def get_entity(self, entity_id: int) -> Entity | None:
        """Obtiene una entidad por su ID."""
        return self._entities.get(entity_id)
    
    def get_entity_by_name(self, name: str) -> Entity | None:
        """Busca una entidad por su nombre."""
        for entity in self._entities.values():
            if entity.name == name:
                return entity
        return None
    
    def get_all_entities(self) -> list[Entity]:
        """Retorna lista con todas las entidades."""
        return list(self._entities.values())
    
    def get_entities_with(self, *component_types: type) -> list[Entity]:
        """Busca entidades que tengan TODOS los componentes especificados."""
        result = []
        for entity in self._entities.values():
            has_all = all(
                entity.has_component(comp_type)
                for comp_type in component_types
            )
            if has_all:
                result.append(entity)
        return result
    
    def entity_count(self) -> int:
        """Retorna el número total de entidades."""
        return len(self._entities)
    
    def clear(self) -> None:
        """Elimina todas las entidades."""
        self._entities.clear()
    
    def clone(self) -> "World":
        """
        Crea una copia profunda del World.
        
        Usado para crear RuntimeWorld en modo PLAY.
        
        Returns:
            Nuevo World con copias de todas las entidades y componentes
        """
        new_world = World()
        
        for entity in self._entities.values():
            # Crear nueva entidad con el mismo nombre
            new_entity = Entity(entity.name)
            
            # Clonar cada componente
            for component in entity.get_all_components():
                cloned_component = self._clone_component(component)
                if cloned_component is not None:
                    new_entity.add_component(cloned_component)
            
            new_world._entities[new_entity.id] = new_entity
        
        return new_world
    
    def _clone_component(self, component: Component) -> Component | None:
        """
        Clona un componente usando to_dict/from_dict.
        
        Args:
            component: Componente a clonar
            
        Returns:
            Copia del componente
        """
        component_class = type(component)
        
        # Usar serialización si está disponible
        if hasattr(component, 'to_dict') and hasattr(component_class, 'from_dict'):
            try:
                data = component.to_dict()
                return component_class.from_dict(data)
            except Exception:
                pass
        
        # Fallback: copia superficial de atributos
        try:
            new_component = component_class.__new__(component_class)
            for attr_name in dir(component):
                if attr_name.startswith('_'):
                    continue
                if callable(getattr(component, attr_name)):
                    continue
                try:
                    value = getattr(component, attr_name)
                    # Copiar listas y diccionarios
                    if isinstance(value, dict):
                        value = value.copy()
                    elif isinstance(value, list):
                        value = value.copy()
                    setattr(new_component, attr_name, value)
                except Exception:
                    pass
            return new_component
        except Exception as e:
            print(f"[WARNING] World.clone: no se pudo clonar {type(component).__name__}: {e}")
            return None
    
    def __repr__(self) -> str:
        return f"World(entities={self.entity_count()})"

    def serialize(self) -> dict:
        """Serializa el World actual para guardado."""
        entities_data = []
        for entity in self._entities.values():
            ent_data = {
                "name": entity.name,
                "components": {}
            }
            
            for component in entity.get_all_components():
                comp_name = type(component).__name__
                # Usar to_dict si existe
                if hasattr(component, 'to_dict'):
                    try:
                        ent_data["components"][comp_name] = component.to_dict()
                    except:
                        pass
                else:
                    # Fallback básico para componentes simples
                    data = {}
                    for attr in dir(component):
                        if not attr.startswith("_") and not callable(getattr(component, attr)):
                            val = getattr(component, attr)
                            if isinstance(val, (int, float, str, bool, list, dict)):
                                data[attr] = val
                    ent_data["components"][comp_name] = data
            
            entities_data.append(ent_data)
            
        return {
            "entities": entities_data,
            "rules": [] # TODO: Serializar reglas del RuleSystem si estuviera integrado en World
        }
