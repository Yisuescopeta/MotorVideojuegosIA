"""
engine/systems/tween_system.py - Sistema de actualizacion de Tweens.

Actualiza propiedades numericas de componentes mediante interpolacion.
Soporta 11 transiciones, 4 modos ease, encadenamiento, paralelismo y loops.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Optional

from engine.components.camera2d import Camera2D
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.components.tween import Tween, TweenStep
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.utils.easing import get_easing

if TYPE_CHECKING:
    from engine.events.signals import SignalRuntime


class TweenSystem:
    """Sistema que actualiza Tweens y muta propiedades de componentes."""

    DEFAULT_COMPONENT_MAP: dict[str, type] = {
        "Transform": Transform,
        "Camera2D": Camera2D,
        "Sprite": Sprite,
    }

    def __init__(
        self,
        signal_runtime: Optional["SignalRuntime"] = None,
        component_map: Optional[dict[str, type]] = None,
    ) -> None:
        self._signal_runtime: Optional["SignalRuntime"] = signal_runtime
        self._component_map: dict[str, type] = (
            dict(component_map) if component_map is not None else dict(self.DEFAULT_COMPONENT_MAP)
        )

    def set_signal_runtime(self, signal_runtime: "SignalRuntime") -> None:
        self._signal_runtime = signal_runtime

    def update(self, world: World, dt: float) -> None:
        """Actualiza todos los Tweens activos del mundo."""
        for entity in world.get_entities_with(Tween):
            tween = entity.get_component(Tween)
            if tween is None or not tween.enabled:
                continue
            self._update_tween(entity, tween, world, dt)

    def _update_tween(self, entity: Entity, tween: Tween, world: World, dt: float) -> None:
        # Autostart en primer frame
        if tween.autostart and not tween._has_autostarted:
            tween._has_autostarted = True
            tween.start()

        if not tween.running or tween.paused:
            return

        dt_scaled = dt * tween.speed_scale

        # Cargar steps al inicio si no hay runtime steps
        if not tween._runtime_steps and tween.steps:
            self._load_next_batch(tween, world)

        if not tween._runtime_steps:
            # No hay steps que procesar
            return

        # Procesar steps activos
        all_done = True
        for step in tween._runtime_steps:
            if step.completed:
                continue

            step.elapsed += dt_scaled
            if step.elapsed < step.delay:
                all_done = False
                continue

            anim_elapsed = step.elapsed - step.delay
            duration = step.duration
            progress = min(1.0, anim_elapsed / duration) if duration > 0 else 1.0

            easing_func = get_easing(step.transition.value, step.ease.value)
            eased_t = easing_func(progress)
            value = step.from_value + (step.to_value - step.from_value) * eased_t
            self._apply_property(world, step, entity, value)

            if progress >= 1.0:
                step.completed = True
            else:
                all_done = False

        # Si todos los steps activos terminaron, cargar siguiente batch
        if all_done:
            tween._runtime_steps.clear()
            if tween._next_step_batch < len(tween.steps):
                self._load_next_batch(tween, world)
            else:
                # Todos los steps terminaron
                self._emit(entity, "finished")
                # Marcar el primer step como completado para backward compat
                if tween.steps:
                    tween.steps[0].completed = True
                tween.loop_count += 1
                if tween.loops > 0 and tween.loop_count < tween.loops:
                    # Aun quedan loops por hacer
                    for s in tween.steps:
                        s.completed = False
                    tween._next_step_batch = 0
                elif tween.loops == -1:
                    # Loop infinito
                    for s in tween.steps:
                        s.completed = False
                    tween._next_step_batch = 0
                else:
                    # loops == 0: una sola ejecucion, detener
                    tween.running = False

    def _load_next_batch(self, tween: Tween, world: World) -> None:
        """Carga el siguiente batch de steps (secuencial o paralelo)."""
        start_idx = tween._next_step_batch
        if start_idx >= len(tween.steps):
            return

        # Primer step del batch
        first_step = tween.steps[start_idx]
        tween._runtime_steps.append(
            dataclasses.replace(first_step, elapsed=0.0, started=False, completed=False)
        )
        tween._next_step_batch = start_idx + 1

        if tween.parallel:
            # En modo paralelo, cargar steps consecutivos mientras duren lo mismo
            while tween._next_step_batch < len(tween.steps) and tween.parallel:
                next_step = tween.steps[tween._next_step_batch]
                tween._runtime_steps.append(
                    dataclasses.replace(next_step, elapsed=0.0, started=False, completed=False)
                )
                tween._next_step_batch += 1

    def _apply_property(
        self,
        world: World,
        step: TweenStep,
        fallback_entity: Entity,
        value: float,
    ) -> bool:
        """Aplica valor a propiedad de componente de entidad."""
        target_name = step.target_entity
        entity = fallback_entity if not target_name else world.get_entity_by_name(target_name)
        if entity is None:
            return False

        prop_path = step.property_path
        if not prop_path:
            return False

        parts = prop_path.split(".")
        if len(parts) < 2:
            return False

        component_name = step.target_component if step.target_component else parts[0]
        if not component_name:
            component_name = parts[0]

        component = self._resolve_component(entity, component_name)
        if component is None:
            return False

        # Si el path tiene mas de 2 partes, navegar hasta la propiedad anidada
        # Si solo tiene 2: "Component.field"
        # Si tiene 3+: "Component.sub.field"
        if len(parts) == 2:
            field_name = parts[1]
            return self._set_component_field(component, field_name, value)

        # Navegar anidacion
        target = component
        for part in parts[1:-1]:
            target = getattr(target, part, None)
            if target is None:
                return False
        field_name = parts[-1]
        return self._set_component_field(target, field_name, value)

    def _set_component_field(self, obj: Any, field_name: str, value: float) -> bool:
        """Establece un campo de componente, con soporte para indices de lista/tupla."""
        # Soporte para indices de lista/tupla (ej: "tint_3")
        if "_" in field_name:
            base_name, index_str = field_name.rsplit("_", 1)
            try:
                index = int(index_str)
            except ValueError:
                base_name = field_name
                index = None
        else:
            base_name = field_name
            index = None

        if not hasattr(obj, base_name):
            return False

        try:
            if index is not None:
                seq = getattr(obj, base_name)
                if isinstance(seq, (list, tuple)):
                    if isinstance(seq, tuple):
                        lst = list(seq)
                        if 0 <= index < len(lst):
                            lst[index] = value
                            setattr(obj, base_name, tuple(lst))
                            return True
                    else:
                        if 0 <= index < len(seq):
                            seq[index] = value
                            return True
            else:
                setattr(obj, base_name, value)
                return True
        except (TypeError, ValueError, IndexError):
            pass

        return False

    def _resolve_component(self, entity: Entity, name: str) -> Any:
        component_type = self._component_map.get(name)
        if component_type is None:
            return None
        return entity.get_component(component_type)

    def _emit(self, entity: Entity, signal_name: str) -> None:
        if self._signal_runtime is None:
            return
        self._signal_runtime.emit(entity.name, signal_name)
