"""
engine/ecs/group_operations.py - Operaciones de gameplay sobre grupos de entidades.

Inspirado en Godot SceneTree pero adaptado a la arquitectura ECS del motor.
No replica SceneTree: solo expone operaciones útiles sobre el GroupRegistry existente.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from engine.ecs.entity import Entity
    from engine.ecs.world import World


class GroupOperations:
    """Fachada ligera para operar sobre grupos de entidades en runtime.

    No posee estado propio; delega en World.group_registry y en los
    sistemas runtime inyectados (ScriptBehaviourSystem, SignalRuntime).
    """

    def __init__(
        self,
        world: World,
        *,
        script_behaviour_system: Any | None = None,
        signal_runtime: Any | None = None,
    ) -> None:
        self._world = world
        self._script_behaviour_system = script_behaviour_system
        self._signal_runtime = signal_runtime

    # --- Consultas (delegadas a GroupRegistry) ---

    def get_entities(self, group_name: str) -> list[Entity]:
        """Devuelve todas las entidades del grupo, ordenadas por nombre."""
        return self._world.group_registry.get_entities(group_name)

    def get_first_entity(self, group_name: str) -> Entity | None:
        """Devuelve la primera entidad activa del grupo, o None."""
        return self._world.group_registry.get_first_entity(group_name)

    def has(self, group_name: str, entity_name: str) -> bool:
        """Comprueba si una entidad (por nombre) pertenece al grupo."""
        return self._world.group_registry.has(group_name, entity_name)

    def has_entity(self, group_name: str, entity: Entity) -> bool:
        """Comprueba si una entidad concreta pertenece al grupo."""
        return self._world.group_registry.has_entity(group_name, entity)

    def count(self, group_name: str) -> int:
        """Número de entidades en el grupo."""
        return self._world.group_registry.count(group_name)

    def is_empty(self, group_name: str) -> bool:
        """Indica si el grupo carece de miembros."""
        return self._world.group_registry.is_empty(group_name)

    def list_groups(self) -> list[str]:
        """Lista los nombres de todos los grupos existentes."""
        return self._world.group_registry.list_groups()

    # --- Operaciones de gameplay ---

    def call_group(
        self,
        group_name: str,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        """Invoca un método ScriptBehaviour en todas las entidades del grupo.

        Retorna el número de invocaciones exitosas.
        """
        if self._script_behaviour_system is None:
            return 0

        invocado = 0
        for entity in self.get_entities(group_name):
            if not entity.active:
                continue
            exito = self._script_behaviour_system.invoke_callable(
                self._world,
                entity.name,
                method_name,
                *args,
                **kwargs,
            )
            if exito:
                invocado += 1
        return invocado

    def emit_group(
        self,
        group_name: str,
        signal_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        """Emite una señal a todas las entidades del grupo.

        Cada entidad actúa como source_id de la señal.  Retorna el número
        total de conexiones ejecutadas.

        Nota: la señal debe estar previamente conectada a targets reales
        (por ejemplo vía SignalRuntime.connect).  emit_group solo dispara.
        """
        if self._signal_runtime is None:
            return 0

        total = 0
        for entity in self.get_entities(group_name):
            if not entity.active:
                continue
            total += self._signal_runtime.emit(
                entity.name,
                signal_name,
                *args,
                **kwargs,
            )
        return total
