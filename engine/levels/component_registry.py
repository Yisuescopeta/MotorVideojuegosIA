"""
engine/levels/component_registry.py - Registro de componentes para instanciación dinámica

PROPÓSITO:
    Mantiene un diccionario de nombre -> clase para poder crear
    componentes desde datos JSON sin hardcodear tipos.

EJEMPLO DE USO:
    registry = ComponentRegistry()
    registry.register("Transform", Transform)
    
    # Crear componente desde datos
    component = registry.create("Transform", {"x": 100, "y": 200})

COMPORTAMIENTO:
    - Registro global por defecto con componentes del motor
    - Permite añadir componentes personalizados
    - Errores claros si el componente no existe
"""

from typing import Any, Dict, Optional, Type

from engine.ecs.component import Component


class ComponentRegistry:
    """
    Registro de tipos de componentes para instanciación dinámica.
    
    Permite crear componentes por nombre desde datos JSON.
    """
    
    def __init__(self) -> None:
        """Inicializa el registro vacío."""
        self._components: Dict[str, Type[Component]] = {}
    
    def register(self, name: str, component_class: Type[Component]) -> None:
        """
        Registra un tipo de componente.
        
        Args:
            name: Nombre del componente (usado en JSON)
            component_class: Clase del componente
        """
        self._components[name] = component_class
    
    def get(self, name: str) -> Optional[Type[Component]]:
        """
        Obtiene una clase de componente por nombre.
        
        Args:
            name: Nombre del componente
            
        Returns:
            Clase del componente o None si no existe
        """
        return self._components.get(name)
    
    def create(self, name: str, data: Dict[str, Any]) -> Optional[Component]:
        """
        Crea una instancia de componente desde datos.
        
        Args:
            name: Nombre del componente
            data: Diccionario con propiedades del componente
            
        Returns:
            Instancia del componente o None si hay error
        """
        component_class = self.get(name)
        
        if component_class is None:
            print(f"[ERROR] ComponentRegistry: componente '{name}' no registrado")
            return None
        
        try:
            # Intentar crear con from_dict si existe
            if hasattr(component_class, 'from_dict'):
                return component_class.from_dict(data)
            
            # Fallback: pasar datos como kwargs al constructor
            return component_class(**data)
            
        except Exception as e:
            print(f"[ERROR] ComponentRegistry: error creando '{name}': {e}")
            return None
    
    def list_registered(self) -> list[str]:
        """
        Lista todos los componentes registrados.
        
        Returns:
            Lista de nombres de componentes
        """
        return list(self._components.keys())


def create_default_registry() -> ComponentRegistry:
    """
    Crea un registro con los componentes predeterminados del motor.
    
    Returns:
        ComponentRegistry con Transform, Sprite, Collider, RigidBody, Animator
    """
    from engine.components.transform import Transform
    from engine.components.sprite import Sprite
    from engine.components.collider import Collider
    from engine.components.rigidbody import RigidBody
    from engine.components.animator import Animator
    
    registry = ComponentRegistry()
    registry.register("Transform", Transform)
    registry.register("Sprite", Sprite)
    registry.register("Collider", Collider)
    registry.register("RigidBody", RigidBody)
    registry.register("Animator", Animator)
    
    return registry
