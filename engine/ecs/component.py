"""
engine/ecs/component.py - Clase base para todos los componentes

PROPÓSITO:
    Define la interfaz base que todos los componentes deben implementar.
    Los componentes son contenedores de DATOS, no de lógica.
    La lógica va en los Systems.

REGLAS:
    - Un componente solo contiene datos
    - Debe ser serializable a diccionario
    - No debe tener efectos secundarios

EJEMPLO DE USO:
    class Transform(Component):
        def __init__(self, x=0, y=0):
            self.x = x
            self.y = y

        def to_dict(self):
            return {"x": self.x, "y": self.y}
"""

from typing import Any


class Component:
    """
    Clase base para todos los componentes del ECS.

    Los componentes son contenedores de datos puros.
    La lógica de procesamiento va en los Systems.

    Todos los componentes deben:
    - Heredar de esta clase
    - Implementar to_dict() para serialización
    - Implementar from_dict() para deserialización
    """

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa el componente a un diccionario.

        Returns:
            Diccionario con todos los datos del componente.
            Las claves deben ser strings, los valores tipos básicos.
        """
        # Implementación por defecto: retorna todos los atributos públicos
        data = {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_")
        }
        data.setdefault("enabled", getattr(self, "enabled", True))
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Component":
        """
        Crea una instancia del componente desde un diccionario.

        Args:
            data: Diccionario con los datos del componente

        Returns:
            Nueva instancia del componente con los datos cargados
        """
        instance = cls()
        if not hasattr(instance, "enabled"):
            setattr(instance, "enabled", True)
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance

    def __repr__(self) -> str:
        """Representación legible del componente para debug."""
        class_name = self.__class__.__name__
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{class_name}({attrs})"
