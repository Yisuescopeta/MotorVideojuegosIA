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

from __future__ import annotations

import warnings

from engine.serialization.json_value import clone_json_value


class LegacyComponentSerializationWarning(UserWarning):
    """Advierte que un componente usa el contrato generico de compatibilidad."""


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

    def to_dict(self) -> dict[str, object]:
        """
        Serializa el componente a un diccionario.

        Returns:
            Diccionario con todos los datos del componente.
            Las claves deben ser strings, los valores tipos básicos serializables.
        """
        warnings.warn(
            (
                f"{type(self).__module__}.{type(self).__name__} usa la serializacion "
                "legacy de Component; implemente to_dict()/from_dict() explicitos"
            ),
            LegacyComponentSerializationWarning,
            stacklevel=2,
        )
        data: dict[str, object] = {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith("_") and not callable(value)
        }
        data.setdefault("enabled", getattr(self, "enabled", True))
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Component":
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

    def clone(self) -> "Component":
        """Crea una copia independiente usando el contrato serializable."""
        payload = clone_json_value(self.to_dict())
        return type(self).from_dict(payload)

    def __repr__(self) -> str:
        """Representación legible del componente para debug."""
        class_name = self.__class__.__name__
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{class_name}({attrs})"


def _serialization_method_owner(component_type: type[Component], method_name: str) -> type | None:
    for base in component_type.__mro__:
        if method_name in base.__dict__:
            return base
    return None


def has_explicit_serialization_contract(component_type: type[Component]) -> bool:
    """Indica si el tipo evita ambos fallbacks genericos de Component."""
    return (
        _serialization_method_owner(component_type, "to_dict") is not Component
        and _serialization_method_owner(component_type, "from_dict") is not Component
    )


def has_explicit_to_dict(component_type: type[Component]) -> bool:
    """Indica si el tipo tiene una ruta de serializacion no generica."""
    return _serialization_method_owner(component_type, "to_dict") is not Component


def is_official_component_type(component_type: type[Component]) -> bool:
    """Identifica componentes mantenidos dentro del paquete oficial."""
    module_name = str(getattr(component_type, "__module__", ""))
    return module_name == "engine.components" or module_name.startswith("engine.components.")
