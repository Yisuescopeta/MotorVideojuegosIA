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

import copy
import itertools
from typing import Any, Iterable, TypeVar

from engine.ecs.component import Component

# TypeVar para tipado genérico de componentes
T = TypeVar("T", bound=Component)

# Contador global para IDs únicos
_ENTITY_ID_COUNTER = itertools.count()


def _generate_entity_id() -> int:
    """Genera un ID único para una nueva entidad."""
    return next(_ENTITY_ID_COUNTER)


def normalize_entity_groups(value: Any) -> tuple[str, ...]:
    """Normaliza grupos de entidad a una tupla ordenada y sin duplicados."""
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        raw_groups = [value]
    else:
        try:
            raw_groups = list(value)
        except TypeError:
            raw_groups = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_group in raw_groups:
        group_name = str(raw_group or "").strip()
        if not group_name or group_name in seen:
            continue
        seen.add(group_name)
        normalized.append(group_name)
    return tuple(normalized)


class Entity:
    """
    Contenedor de componentes identificado por un ID único.

    Una entidad es solo un ID con un nombre y una colección de componentes.
    No contiene lógica de juego, solo organiza datos.
    """

    _TRACKED_FIELDS = {
        "name",
        "active",
        "tag",
        "layer",
        "groups",
        "parent_name",
        "prefab_instance",
        "prefab_source_path",
        "prefab_root_name",
    }

    def __init__(self, name: str = "Entity") -> None:
        """
        Crea una nueva entidad con un ID único.

        Args:
            name: Nombre legible para identificar la entidad (debug)
        """
        object.__setattr__(self, "_owner_world", None)
        object.__setattr__(self, "_notifications_suspended", True)
        self.id: int = _generate_entity_id()
        self.serialized_id: str | None = None
        self.name: str = name
        self.active: bool = True
        self.tag: str = "Untagged"
        self.layer: str = "Default"
        self.groups: tuple[str, ...] = ()
        self.parent_name: str | None = None
        self.prefab_instance: dict[str, Any] | None = None
        self.prefab_source_path: str | None = None
        self.prefab_root_name: str | None = None
        self._components: dict[type, Component] = {}
        self._component_types_by_name: dict[str, type] = {}
        self._component_metadata: dict[type, dict[str, Any]] = {}
        object.__setattr__(self, "_notifications_suspended", False)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "groups":
            value = normalize_entity_groups(value)
        notifications_suspended = bool(getattr(self, "_notifications_suspended", True))
        tracked = name in self._TRACKED_FIELDS and not notifications_suspended and hasattr(self, name)
        previous = getattr(self, name, None) if tracked else None
        object.__setattr__(self, name, value)
        if tracked and previous != value:
            self._notify_owner_world(
                "entity_field_changed",
                field=name,
                previous=previous,
                current=value,
            )

    def _set_owner_world(self, world: Any | None) -> None:
        object.__setattr__(self, "_owner_world", world)

    def _notify_owner_world(self, event: str, **payload: Any) -> None:
        owner_world = getattr(self, "_owner_world", None)
        if owner_world is not None and hasattr(owner_world, "_on_entity_changed"):
            owner_world._on_entity_changed(self, event, **payload)

    def add_component(self, component: Component, metadata: dict[str, Any] | None = None) -> None:
        """
        Añade un componente a la entidad.

        Solo puede haber un componente de cada tipo por entidad.
        Si ya existe un componente del mismo tipo, se reemplaza.

        Args:
            component: Instancia del componente a añadir
        """
        component_type = type(component)
        previous_component = self._components.get(component_type)
        self._components[component_type] = component
        self._component_types_by_name[component_type.__name__] = component_type
        self._component_metadata[component_type] = copy.deepcopy(metadata or {})
        self._notify_owner_world(
            "component_added",
            component_type=component_type,
            previous_component=previous_component,
            component=component,
        )

    def get_component(self, component_type: type[T]) -> T | None:
        """
        Obtiene un componente por su tipo.

        Si no existe exactamente, busca una subclase registrada.

        Args:
            component_type: Clase del componente a buscar

        Returns:
            El componente si existe, None en caso contrario
        """
        comp = self._components.get(component_type)
        if comp is not None:
            return comp  # type: ignore
        # Buscar subclase registrada
        for registered_type, instance in self._components.items():
            if issubclass(registered_type, component_type):
                return instance  # type: ignore
        return None

    def get_component_exact(self, component_type: type[T]) -> T | None:
        """Obtiene un componente solo si el tipo coincide exactamente."""
        return self._components.get(component_type)  # type: ignore

    def get_component_by_name(self, component_name: str) -> Component | None:
        """Obtiene un componente por el nombre de su clase."""
        component_type = self._component_types_by_name.get(component_name)
        if component_type is None:
            return None
        return self._components.get(component_type)

    def has_component(self, component_type: type) -> bool:
        """
        Verifica si la entidad tiene un componente de un tipo específico.

        Args:
            component_type: Clase del componente a verificar

        Returns:
            True si el componente existe, False en caso contrario
        """
        return component_type in self._components

    def has_enabled_component(self, component_type: type) -> bool:
        component = self._components.get(component_type)
        if component is None:
            return False
        return bool(getattr(component, "enabled", True))

    def remove_component(self, component_type: type) -> None:
        """
        Elimina un componente de la entidad.

        Args:
            component_type: Clase del componente a eliminar
        """
        if component_type in self._components:
            removed_component = self._components[component_type]
            del self._components[component_type]
            component_name = component_type.__name__
            if self._component_types_by_name.get(component_name) is component_type:
                del self._component_types_by_name[component_name]
            self._notify_owner_world(
                "component_removed",
                component_type=component_type,
                component=removed_component,
            )
        if component_type in self._component_metadata:
            del self._component_metadata[component_type]

    def get_all_components(self) -> list[Component]:
        """
        Retorna una lista con todos los componentes de la entidad.

        Returns:
            Lista de todos los componentes
        """
        return list(self.iter_components())

    def iter_components(self) -> Iterable[Component]:
        """Itera todos los componentes sin crear una lista temporal."""
        return self._components.values()

    def get_component_metadata(self, component_type: type[T]) -> dict[str, Any]:
        return copy.deepcopy(self._component_metadata.get(component_type, {}))

    def set_component_metadata(self, component_type: type[T], metadata: dict[str, Any] | None) -> None:
        if component_type not in self._components:
            return
        self._component_metadata[component_type] = copy.deepcopy(metadata or {})
        self._notify_owner_world(
            "component_metadata_changed",
            component_type=component_type,
        )

    def get_component_metadata_by_name(self, component_name: str) -> dict[str, Any]:
        component_type = self._component_types_by_name.get(component_name)
        if component_type is not None:
            return self.get_component_metadata(component_type)
        return {}

    def to_dict(self) -> dict[str, Any]:
        """
        Serializa la entidad a un diccionario.

        Returns:
            Diccionario con id, name y componentes serializados
        """
        data = {
            "id": self.serialized_id if self.serialized_id else self.id,
            "name": self.name,
            "active": self.active,
            "tag": self.tag,
            "layer": self.layer,
            "components": {comp_type.__name__: comp.to_dict() for comp_type, comp in self._components.items()},
            "component_metadata": {
                comp_type.__name__: copy.deepcopy(self._component_metadata.get(comp_type, {}))
                for comp_type in self._components.keys()
                if self._component_metadata.get(comp_type)
            },
        }
        if self.groups:
            data["groups"] = list(self.groups)
        if self.parent_name is not None:
            data["parent"] = self.parent_name
        if self.prefab_instance is not None:
            data["prefab_instance"] = self.prefab_instance
        if self.prefab_source_path is not None:
            data["prefab_source_path"] = self.prefab_source_path
        if self.prefab_root_name is not None:
            data["prefab_root_name"] = self.prefab_root_name
        if not data["component_metadata"]:
            del data["component_metadata"]
        return data

    def __repr__(self) -> str:
        """Representación legible de la entidad para debug."""
        comp_names = [t.__name__ for t in self._components.keys()]
        return f"Entity(id={self.id}, name='{self.name}', components={comp_names})"
