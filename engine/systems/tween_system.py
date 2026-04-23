"""
engine/systems/tween_system.py - Sistema de actualizacion de Tweens.

Actualiza propiedades numericas de componentes mediante interpolacion.
Soporta paths simples del tipo "Componente.propiedad" o "Componente.propiedad_indice".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from engine.components.camera2d import Camera2D
from engine.components.sprite import Sprite
from engine.components.tween import Tween
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.utils.easing import get_easing

if TYPE_CHECKING:
    from engine.events.signals import SignalRuntime


class TweenSystem:
    """Sistema que actualiza Tweens y muta propiedades de componentes."""

    def __init__(self, signal_runtime: Optional["SignalRuntime"] = None) -> None:
        self._signal_runtime: Optional["SignalRuntime"] = signal_runtime

    def set_signal_runtime(self, signal_runtime: "SignalRuntime") -> None:
        self._signal_runtime = signal_runtime

    def update(self, world: World, dt: float) -> None:
        """Actualiza todos los Tweens activos del mundo."""
        for entity in world.get_entities_with(Tween):
            tween = entity.get_component(Tween)
            if tween is None or not tween.enabled:
                continue
            self._update_tween(entity, tween, dt)

    def _update_tween(self, entity: Entity, tween: Tween, dt: float) -> None:
        # Autostart en primer frame
        if tween.autostart and not tween._has_autostarted:
            tween._has_autostarted = True
            tween.start()

        if not tween.is_running:
            return

        tween._elapsed += dt
        progress = tween.progress

        easing_func = get_easing(tween.transition)
        eased_t = easing_func(progress)
        current_value = tween.from_value + (tween.to_value - tween.from_value) * eased_t

        self._apply_value(entity, tween.property_path, current_value)

        if progress >= 1.0:
            self._emit(entity, "finished")
            if tween.one_shot:
                tween.stop()
                tween._is_finished = True
            else:
                excess = tween._elapsed - tween.duration
                tween._elapsed = max(0.0, excess)
                # Reaplicar valor con el progreso reiniciado
                new_progress = tween.progress
                new_eased_t = get_easing(tween.transition)(new_progress)
                new_value = tween.from_value + (tween.to_value - tween.from_value) * new_eased_t
                self._apply_value(entity, tween.property_path, new_value)

    def _apply_value(self, entity: Entity, property_path: str, value: float) -> bool:
        if not property_path:
            return False

        parts = property_path.split(".")
        if len(parts) < 2:
            return False

        component_name = parts[0]
        field_name = parts[1]

        component = self._resolve_component(entity, component_name)
        if component is None:
            return False

        # Soporte para indices de lista/tupla (ej: "Sprite.tint_3")
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

        if not hasattr(component, base_name):
            return False

        try:
            if index is not None:
                seq = getattr(component, base_name)
                if isinstance(seq, (list, tuple)):
                    if isinstance(seq, tuple):
                        # Reconstruir tupla inmutable
                        lst = list(seq)
                        if 0 <= index < len(lst):
                            lst[index] = max(0, min(255, int(value))) if base_name == "tint" else value
                            setattr(component, base_name, tuple(lst))
                            return True
                    else:
                        if 0 <= index < len(seq):
                            seq[index] = max(0, min(255, int(value))) if base_name == "tint" else value
                            return True
            else:
                setattr(component, base_name, value)
                return True
        except (TypeError, ValueError, IndexError):
            pass

        return False

    def _resolve_component(self, entity: Entity, name: str) -> Any:
        mapping: dict[str, type] = {
            "Transform": Transform,
            "Camera2D": Camera2D,
            "Sprite": Sprite,
        }
        component_type = mapping.get(name)
        if component_type is None:
            return None
        return entity.get_component(component_type)

    def _emit(self, entity: Entity, signal_name: str) -> None:
        if self._signal_runtime is None:
            return
        self._signal_runtime.emit(entity.name, signal_name)
