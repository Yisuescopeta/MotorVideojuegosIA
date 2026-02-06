"""
engine/ecs/entity.py - Clase Entity del sistema ECS

PROPÓSITO:
    Una Entity es un contenedor que agrupa componentes bajo un ID único.
    En sí misma, una entidad no tiene datos ni comportamiento,
    solo sirve para organizar componentes relacionados.

PROPIEDADES:
    - id (int): Identificador único auto-generado
    - name (str): Nombre legible para debug
    - components (dict): Mapa de tipo -> componente

EJEMPLO DE USO:
    player = Entity("Player")
    player.add_component(Transform(x=100, y=200))
    player.add_component(Sprite(texture="player.png"))
    
    transform = player.get_component(Transform)
    print(transform.x)  # 100
"""

from typing import Any, TypeVar

from engine.ecs.component import Component

# TypeVar para tipado genérico de componentes
T = TypeVar("T", bound=Component)

# Contador global para IDs únicos
_next_entity_id: int = 0


def _generate_entity_id() -> int:
    """Genera un ID único para una nueva entidad."""
    global _next_entity_id
    entity_id = _next_entity_id
    _next_entity_id += 1
    return entity_id


class Entity:
    """
    Contenedor de componentes identificado por un ID único.
    
    Una entidad es solo un ID con un nombre y una colección de componentes.
    No contiene lógica de juego, solo organiza datos.
    """
    
    def __init__(self, name: str = "Entity") -> None:
        """
        Crea una nueva entidad con un ID único.
        
        Args:
            name: Nombre legible para identificar la entidad (debug)
        """
        self.id: int = _generate_entity_id()
        self.name: str = name
        self._components: dict[type, Component] = {}
    
    def add_component(self, component: Component) -> None:
        """
        Añade un componente a la entidad.
        
        Solo puede haber un componente de cada tipo por entidad.
        Si ya existe un componente del mismo tipo, se reemplaza.
        
        Args:
            component: Instancia del componente a añadir
        """
        component_type = type(component)
        self._components[component_type] = component
    
    def get_component(self, component_type: type[T]) -> T | None:
        """
        Obtiene un componente por su tipo.
        
        Args:
            component_type: Clase del componente a buscar
            
        Returns:
            El componente si existe, None en caso contrario
        """
        return self._components.get(component_type)  # type: ignore
    
    def has_component(self, component_type: type) -> bool:
        """
        Verifica si la entidad tiene un componente de un tipo específico.
        
        Args:
            component_type: Clase del componente a verificar
            
        Returns:
            True si el componente existe, False en caso contrario
        """
        return component_type in self._components
    
    def remove_component(self, component_type: type) -> None:
        """
        Elimina un componente de la entidad.
        
        Args:
            component_type: Clase del componente a eliminar
        """
        if component_type in self._components:
            del self._components[component_type]
    
    def get_all_components(self) -> list[Component]:
        """
        Retorna una lista con todos los componentes de la entidad.
        
        Returns:
            Lista de todos los componentes
        """
        return list(self._components.values())
    
    def to_dict(self) -> dict[str, Any]:
        """
        Serializa la entidad a un diccionario.
        
        Returns:
            Diccionario con id, name y componentes serializados
        """
        return {
            "id": self.id,
            "name": self.name,
            "components": {
                comp_type.__name__: comp.to_dict()
                for comp_type, comp in self._components.items()
            }
        }
    
    def __repr__(self) -> str:
        """Representación legible de la entidad para debug."""
        comp_names = [t.__name__ for t in self._components.keys()]
        return f"Entity(id={self.id}, name='{self.name}', components={comp_names})"
